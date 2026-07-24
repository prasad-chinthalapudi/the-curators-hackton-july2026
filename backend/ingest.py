"""PIH Ingestion pipeline (Person A) — A3/A4/A5/A6.

Turns raw project files under UPLOADS into:
  - LanceDB `chunks`  table (text + image_caption rows, vector[3072])
  - LanceDB `projects` table (one row per project, summary + tech_tags)
  - NetworkX graph.json (Person->Project role edges)

Scale guards are built in, not bolted on:
  - subset-first (MAX_FILES cap, --full to run everything)
  - incremental manifest (hash each file, skip already-processed)
  - retry/backoff on every API call (via openai_utils)
  - captioning cap + tiny-image skip + running cost print + COST_CEILING_USD

Run:
  python -m backend.ingest              # subset (MAX_FILES), captions on
  python -m backend.ingest --full       # everything
  python -m backend.ingest --no-caption # text only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field

from . import config
from . import graph as G
from . import openai_utils as ou

log = logging.getLogger("pih.ingest")

# --- rough cost estimates (guard proxies, not billing truth) ---
EMBED_USD_PER_1K_TOKENS = 0.00013     # text-embedding-3-large
CAPTION_USD_PER_IMAGE = 0.01          # vision call flat estimate
EXTRACT_USD_PER_PROJECT = 0.02        # per-project summary chat estimate

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:  # tiktoken missing/unavailable — fall back to word count
    _ENC = None


def _count_tokens(text: str) -> int:
    if _ENC is not None:
        try:
            return len(_ENC.encode(text))
        except Exception:
            pass
    return max(1, len(text.split()))


# ---------------------------------------------------------------------------
# Cost / count tracker — prints running totals, enforces caption cost ceiling.
# ---------------------------------------------------------------------------
@dataclass
class CostTracker:
    files: int = 0
    chunks: int = 0
    images_captioned: int = 0
    images_skipped: int = 0
    embed_tokens: int = 0
    est_embed_usd: float = 0.0
    est_caption_usd: float = 0.0
    est_extract_usd: float = 0.0

    @property
    def total_usd(self) -> float:
        return self.est_embed_usd + self.est_caption_usd + self.est_extract_usd

    def add_embed(self, tokens: int) -> None:
        self.embed_tokens += tokens
        self.est_embed_usd += tokens / 1000.0 * EMBED_USD_PER_1K_TOKENS

    def add_caption(self) -> None:
        self.images_captioned += 1
        self.est_caption_usd += CAPTION_USD_PER_IMAGE

    def add_extract(self) -> None:
        self.est_extract_usd += EXTRACT_USD_PER_PROJECT

    def caption_budget_left(self) -> bool:
        """True while captioning is still under the cost ceiling."""
        return self.total_usd < config.COST_CEILING_USD

    def print_running(self, note: str = "") -> None:
        log.info(
            "[running] files=%d chunks=%d captioned=%d skipped_imgs=%d "
            "embed_tokens=%d est_cost=$%.3f (embed $%.3f / caption $%.3f / extract $%.3f) %s",
            self.files, self.chunks, self.images_captioned, self.images_skipped,
            self.embed_tokens, self.total_usd, self.est_embed_usd,
            self.est_caption_usd, self.est_extract_usd, note,
        )


# ---------------------------------------------------------------------------
# Manifest — hash each file; skip files already processed (incremental/resumable).
# ---------------------------------------------------------------------------
def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest(path: str = config.MANIFEST) -> dict:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("manifest unreadable (%s); starting fresh.", e)
    return {}


def save_manifest(manifest: dict, path: str = config.MANIFEST) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # atomic-ish so an interrupted run doesn't corrupt it


def doc_id_for(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    return slug or hashlib.sha1(filename.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Chunking — structure-aware, ~CHUNK_TOKENS with CHUNK_OVERLAP. Pure/testable.
# source_ref shape: "filename · heading"  (falls back to "filename · part N").
# ---------------------------------------------------------------------------
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _split_sections(md: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) sections by ATX headers."""
    sections: list[tuple[str, str]] = []
    current_heading = ""
    buf: list[str] = []
    for line in md.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if buf:
                sections.append((current_heading, "\n".join(buf).strip()))
                buf = []
            current_heading = m.group(2).strip()
        else:
            buf.append(line)
    if buf:
        sections.append((current_heading, "\n".join(buf).strip()))
    return [(h, b) for h, b in sections if b]


def _window_tokens(text: str, size: int, overlap: int) -> list[str]:
    """Pack text into ~size-token windows with `overlap` tokens shared."""
    if _ENC is not None:
        try:
            toks = _ENC.encode(text)
            if len(toks) <= size:
                return [text]
            out, start = [], 0
            step = max(1, size - overlap)
            while start < len(toks):
                out.append(_ENC.decode(toks[start:start + size]))
                start += step
            return out
        except Exception:
            pass
    # fallback: word-based windows
    words = text.split()
    if len(words) <= size:
        return [text]
    out, start = [], 0
    step = max(1, size - overlap)
    while start < len(words):
        out.append(" ".join(words[start:start + size]))
        start += step
    return out


def chunk_markdown(md: str, filename: str,
                   size: int = config.CHUNK_TOKENS,
                   overlap: int = config.CHUNK_OVERLAP) -> list[dict]:
    """Return list of {text, source_ref} chunks. source_ref = 'filename · heading'."""
    base = os.path.basename(filename)
    chunks: list[dict] = []
    sections = _split_sections(md) or [("", md.strip())]
    for i, (heading, body) in enumerate(sections):
        if not body.strip():
            continue
        label = heading if heading else f"part {i + 1}"
        windows = _window_tokens(body, size, overlap)
        for w, piece in enumerate(windows):
            ref = f"{base} · {label}"
            if len(windows) > 1:
                ref += f" ({w + 1}/{len(windows)})"
            chunks.append({"text": piece.strip(), "source_ref": ref})
    return [c for c in chunks if c["text"]]


# ---------------------------------------------------------------------------
# LanceDB — enforce vector[EMBED_DIM] via explicit pyarrow schema.
# ---------------------------------------------------------------------------
def _lance_connect():
    import lancedb
    os.makedirs(config.LANCEDB, exist_ok=True)
    return lancedb.connect(config.LANCEDB)


def _chunks_schema():
    import pyarrow as pa
    return pa.schema([
        ("id", pa.string()),
        ("project", pa.string()),
        ("doc_id", pa.string()),
        ("source_ref", pa.string()),
        ("chunk_type", pa.string()),
        ("text", pa.string()),
        ("image_path", pa.string()),  # nullable; None for text rows
        ("vector", pa.list_(pa.float32(), config.EMBED_DIM)),
    ])


def _projects_schema():
    import pyarrow as pa
    return pa.schema([
        ("project", pa.string()),
        ("client", pa.string()),
        ("primary_doc_id", pa.string()),
        ("summary", pa.string()),
        ("tech_tags", pa.string()),
        ("vector", pa.list_(pa.float32(), config.EMBED_DIM)),
    ])


def _ensure_table(db, name: str, schema):
    import pyarrow as pa
    if name in db.table_names():
        return db.open_table(name)
    return db.create_table(name, schema=schema)


def _insert_rows(table, rows: list[dict], schema) -> None:
    import pyarrow as pa
    if not rows:
        return
    table.add(pa.Table.from_pylist(rows, schema=schema))


def _sql_str(value: str) -> str:
    """Escape a string for a LanceDB SQL predicate (single-quote doubling)."""
    return "'" + str(value).replace("'", "''") + "'"


def _delete_where(table, predicate: str) -> None:
    """Delete rows matching predicate; tolerate an empty table."""
    try:
        table.delete(predicate)
    except Exception as e:
        log.warning("delete(%s) failed (%s) - continuing.", predicate, e)


# ---------------------------------------------------------------------------
# Docling parse — Markdown + extracted images. Every call guarded.
# ---------------------------------------------------------------------------
_converter = None


def _get_converter():
    global _converter
    if _converter is not None:
        return _converter
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        opts = PdfPipelineOptions()
        opts.generate_picture_images = True
        opts.images_scale = 2.0
        _converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
    except Exception as e:
        log.warning("Docling image-enabled converter setup failed (%s); using default converter.", e)
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
    return _converter


def parse_file(path: str, doc_id: str) -> tuple[str, list[dict]]:
    """Return (markdown, images). images = [{image_path, caption, page}]. Never raises."""
    try:
        result = _get_converter().convert(path)
        doc = result.document
    except Exception as e:
        log.error("Docling parse failed for %s: %s", path, e)
        return "", []

    try:
        md = doc.export_to_markdown()
    except Exception as e:
        log.error("export_to_markdown failed for %s: %s", path, e)
        md = ""

    images = _extract_images(doc, doc_id)
    return md, images


def _extract_images(doc, doc_id: str) -> list[dict]:
    """Save embedded images >= MIN_IMAGE_BYTES to IMAGES/. Reading order preserved."""
    os.makedirs(config.IMAGES, exist_ok=True)
    out: list[dict] = []
    pictures = getattr(doc, "pictures", None) or []
    for n, pic in enumerate(pictures):
        try:
            pil = pic.get_image(doc)
            if pil is None:
                continue
            img_path = os.path.join(config.IMAGES, f"{doc_id}_{n}.png")
            pil.save(img_path, format="PNG")
            size = os.path.getsize(img_path)
            if size < config.MIN_IMAGE_BYTES:
                os.remove(img_path)  # skip tiny/decorative images
                out.append({"image_path": None, "caption": "", "page": None, "skipped": True})
                continue
            try:
                caption = pic.caption_text(doc) or ""
            except Exception:
                caption = ""
            page = None
            try:
                if getattr(pic, "prov", None):
                    page = pic.prov[0].page_no
            except Exception:
                pass
            out.append({"image_path": img_path, "caption": caption, "page": page, "skipped": False})
        except Exception as e:
            log.warning("image %d extract failed for %s: %s", n, doc_id, e)
    return out


# ---------------------------------------------------------------------------
# A5 — Group flat files into projects (dataset is 898 flat mixed-format files).
# Path chosen: filename-stem clustering, with an LLM grouping fallback if the
# heuristic looks pathological (1 blob or N singletons).
# ---------------------------------------------------------------------------
# Strip version/date noise AND common document-type trailing words so that
# "Contoso_Forecasting_deck.pptx" and "Contoso_Forecasting_v3.pdf" collapse to
# the same project key. NOTE: this heuristic is tuned to a GUESS at the flat
# 898-file naming; re-tune `_DOC_NOISE`/prefix width once real filenames land,
# or rely on the _llm_group() fallback.
_VERSION_NOISE = re.compile(
    r"(_?v\d+|_?final|_?draft|_?copy|_?\d{4}[-_]?\d{2}[-_]?\d{2}|\(\d+\))",
    re.IGNORECASE,
)
_DOC_NOISE = re.compile(
    r"\b(deck|slides?|presentation|pitch|proposal|sow|onepager|one\s*pager|"
    r"casestudy|case\s*study|report|summary|overview)\b",
    re.IGNORECASE,
)


def _normalize_stem(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = _VERSION_NOISE.sub("", stem)
    stem = re.sub(r"[^a-zA-Z0-9]+", " ", stem)
    stem = _DOC_NOISE.sub("", stem)
    stem = re.sub(r"\s+", " ", stem).strip().lower()
    return stem


def _prefix_key(filename: str, words: int = 2) -> str:
    toks = _normalize_stem(filename).split()
    return " ".join(toks[:words]) if toks else _normalize_stem(filename)


def group_files(filenames: list[str]) -> dict[str, list[str]]:
    """Group flat filenames into projects. Returns {project_key: [filenames]}."""
    groups: dict[str, list[str]] = {}
    for fn in filenames:
        key = _prefix_key(fn) or doc_id_for(fn)
        groups.setdefault(key, []).append(fn)

    n = len(filenames)
    distinct = len(groups)
    # Only treat as pathological on a LARGE set: everything collapsing to one
    # blob, or every file its own singleton. A small subset legitimately having
    # 1-2 groups is fine and must NOT trigger an LLM call.
    pathological = (n >= 8 and distinct <= 1) or (n >= 8 and distinct >= n)
    if pathological:
        log.warning("group_files: filename heuristic looks off (%d files -> %d groups); "
                    "trying one LLM grouping call.", n, distinct)
        llm = _llm_group(filenames)
        if llm:
            return llm
    log.info("group_files: %d files -> %d projects (filename-stem clustering).", n, distinct)
    return groups


def _llm_group(filenames: list[str]) -> dict[str, list[str]] | None:
    """Fallback: ask the model to cluster filenames into projects. None on failure."""
    try:
        listing = "\n".join(f"- {os.path.basename(f)}" for f in filenames)
        system = ("You cluster deck/document filenames into distinct client projects. "
                  "Return JSON {\"groups\":[{\"project\":str,\"files\":[str]}]}. "
                  "Every input filename must appear in exactly one group.")
        data = ou.chat_json(system, f"Filenames:\n{listing}", config.GEN_MODEL_PRIMARY)
        by_base = {os.path.basename(f): f for f in filenames}
        groups: dict[str, list[str]] = {}
        for grp in data.get("groups", []):
            proj = str(grp.get("project", "")).strip() or "unknown"
            for b in grp.get("files", []):
                full = by_base.get(os.path.basename(str(b)))
                if full:
                    groups.setdefault(proj, []).append(full)
        # ensure nothing dropped
        placed = {f for fs in groups.values() for f in fs}
        for f in filenames:
            if f not in placed:
                groups.setdefault("unassigned", []).append(f)
        return groups or None
    except Exception as e:
        log.warning("_llm_group failed (%s); keeping filename heuristic.", e)
        return None


# ---------------------------------------------------------------------------
# A5 — per-project extraction (one chat_json call) -> summary/tags/people.
# ---------------------------------------------------------------------------
_EXTRACT_SYSTEM = (
    "You extract structured project metadata from combined project documents. "
    "Return JSON with EXACTLY these keys: "
    '{"project":str,"client":str|null,"date":str|null,'
    '"summary":"2-4 sentences: domain, problem, tech stack, techniques, outcomes",'
    '"tech_tags":[str],'
    '"people":[{"name":str,"role":"led|signed_deal|data_scientist|data_engineer|pm","email":str|null}]}. '
    "tech_tags must list concrete technologies/frameworks/techniques actually mentioned. "
    "Use null when unknown; never invent people or clients."
)


def extract_project(project_key: str, combined_md: str) -> dict:
    """One extraction call over combined Markdown. Returns a dict (safe defaults on failure)."""
    user = f"Project key: {project_key}\n\nCombined documents (truncated):\n{combined_md[:24000]}"
    try:
        data = ou.chat_json(_EXTRACT_SYSTEM, user, config.GEN_MODEL_PRIMARY)
    except Exception as e:
        log.error("extract_project failed for %s: %s", project_key, e)
        data = {}
    data.setdefault("project", project_key)
    data.setdefault("client", None)
    data.setdefault("date", None)
    data.setdefault("summary", "")
    tags = data.get("tech_tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    data["tech_tags"] = tags
    data.setdefault("people", [])
    return data


# ---------------------------------------------------------------------------
# Main pipeline.
# ---------------------------------------------------------------------------
SUPPORTED_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".md", ".html", ".htm", ".csv", ".txt"}


def _list_upload_files(uploads: str) -> list[str]:
    out = []
    for root, _, files in os.walk(uploads):
        for fn in files:
            if os.path.splitext(fn)[1].lower() in SUPPORTED_EXTS:
                out.append(os.path.join(root, fn))
    return sorted(out)


def run(full: bool = False, max_files: int | None = None, caption: bool = True) -> CostTracker:
    tracker = CostTracker()
    manifest = load_manifest()
    db = _lance_connect()
    chunks_tbl = _ensure_table(db, "chunks", _chunks_schema())
    projects_tbl = _ensure_table(db, "projects", _projects_schema())
    g = G.load_graph()  # accumulate onto any existing graph

    all_files = _list_upload_files(config.UPLOADS)
    if not full:
        cap = max_files if max_files is not None else config.MAX_FILES
        all_files = all_files[:cap]
    log.info("ingest: %d candidate files (full=%s, caption=%s)", len(all_files), full, caption)

    # --- A5 grouping decided up front so chunks carry the right project label ---
    groups = group_files(all_files)
    file_to_project = {f: proj for proj, fs in groups.items() for f in fs}
    log.info("=== project -> files mapping (%d projects) ===", len(groups))
    for proj, fs in groups.items():
        log.info("  [%s] <- %s", proj, ", ".join(os.path.basename(f) for f in fs))

    project_md: dict[str, list[str]] = {}   # accumulate markdown per project for extraction
    project_docs: dict[str, list[str]] = {}  # doc_ids per project (for primary_doc_id)
    changed_groups: set[str] = set()         # group keys with >=1 (re)processed file this run
    # Groups already extracted in a prior run (group_key -> canonical project name),
    # stored under a reserved manifest key so unchanged re-runs skip re-extraction.
    extracted_groups: dict[str, str] = manifest.get("__extracted_groups__", {})

    # --- Per-file: parse -> chunk -> embed -> insert (A3), caption (A4) ---
    for path in all_files:
        doc_id = doc_id_for(path)
        project = file_to_project.get(path, "unknown")
        h = file_hash(path)
        if manifest.get(path, {}).get("hash") == h:
            log.info("skip (unchanged): %s", os.path.basename(path))
            # still need its markdown for project extraction on this run
            cached_md = manifest[path].get("markdown", "")
            if cached_md:
                project_md.setdefault(project, []).append(cached_md)
            project_docs.setdefault(project, []).append(doc_id)
            continue

        md, images = parse_file(path, doc_id)
        project_md.setdefault(project, []).append(md)
        project_docs.setdefault(project, []).append(doc_id)
        changed_groups.add(project)
        # Re-ingest of a changed file: drop its old rows first so we don't duplicate.
        _delete_where(chunks_tbl, f"doc_id = {_sql_str(doc_id)}")

        # A3: chunk + embed text rows
        chunk_recs = chunk_markdown(md, path)
        if chunk_recs:
            texts = [c["text"] for c in chunk_recs]
            try:
                vectors = ou.embed_texts(texts)
            except Exception as e:
                log.error("embed failed for %s: %s; skipping its text rows.", os.path.basename(path), e)
                vectors = []
            if len(vectors) == len(texts):
                for i, (c, vec) in enumerate(zip(chunk_recs, vectors)):
                    if len(vec) != config.EMBED_DIM:
                        log.error("vector dim %d != EMBED_DIM %d; skipping row.", len(vec), config.EMBED_DIM)
                        continue
                    tracker.add_embed(_count_tokens(c["text"]))
                    _insert_rows(chunks_tbl, [{
                        "id": f"{doc_id}_c{i}",
                        "project": project,
                        "doc_id": doc_id,
                        "source_ref": c["source_ref"],
                        "chunk_type": "text",
                        "text": c["text"],
                        "image_path": None,
                        "vector": vec,
                    }], _chunks_schema())
                    tracker.chunks += 1

        # A4: caption up to MAX_IMAGES_PER_DOC images (cost-guarded)
        if caption and config.CAPTION_ENABLED:
            captioned_this_doc = 0
            for img in images:
                if img.get("skipped") or not img.get("image_path"):
                    tracker.images_skipped += 1
                    continue
                if captioned_this_doc >= config.MAX_IMAGES_PER_DOC:
                    break
                if not tracker.caption_budget_left():
                    log.warning("COST_CEILING_USD ($%d) reached at $%.2f; stopping CAPTIONING "
                                "(text ingest continues).", config.COST_CEILING_USD, tracker.total_usd)
                    break
                cap_text = ou.caption_image(img["image_path"], config.GEN_MODEL_PRIMARY)
                if not cap_text:
                    continue
                try:
                    cvec = ou.embed_texts([cap_text])[0]
                except Exception as e:
                    log.error("caption embed failed: %s", e)
                    continue
                if len(cvec) != config.EMBED_DIM:
                    continue
                nearby = img.get("caption") or ""
                full_text = (nearby + " " + cap_text).strip() if nearby else cap_text
                tracker.add_embed(_count_tokens(full_text))
                tracker.add_caption()
                captioned_this_doc += 1
                _insert_rows(chunks_tbl, [{
                    "id": f"{doc_id}_img{captioned_this_doc}",
                    "project": project,
                    "doc_id": doc_id,
                    "source_ref": f"{os.path.basename(path)} · figure {captioned_this_doc}",
                    "chunk_type": "image_caption",
                    "text": full_text,
                    "image_path": img["image_path"],
                    "vector": cvec,
                }], _chunks_schema())
                tracker.chunks += 1

        manifest[path] = {"hash": h, "doc_id": doc_id, "project": project,
                          "markdown": md, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_manifest(manifest)  # persist after each file -> resumable
        tracker.files += 1
        tracker.print_running(note=os.path.basename(path))

    # --- A5: per-project extraction -> graph + projects table ---
    log.info("=== extracting %d projects ===", len(project_md))
    for project, md_list in project_md.items():
        # Skip re-extraction when nothing in this group changed AND it was already
        # extracted on a prior run -> unchanged re-runs are near-instant, no dup rows.
        if project not in changed_groups and project in extracted_groups:
            log.info("skip extraction (unchanged group): %s", project)
            continue
        combined = "\n\n---\n\n".join(m for m in md_list if m)
        if not combined.strip():
            log.warning("project '%s' has no markdown; skipping extraction.", project)
            continue
        meta = extract_project(project, combined)
        tracker.add_extract()

        proj_name = meta.get("project") or project
        # Upsert: clear any prior rows for this project name before re-inserting.
        _delete_where(projects_tbl, f"project = {_sql_str(proj_name)}")
        G.add_project(g, proj_name, client=meta.get("client"), date=meta.get("date"))
        for person in meta.get("people", []):
            name = (person.get("name") or "").strip()
            role = (person.get("role") or "").strip()
            if name and role:
                G.add_person_edge(g, name, proj_name, role, email=person.get("email"))

        # embed summary -> projects row
        summary = meta.get("summary") or ""
        tags = meta.get("tech_tags") or []
        tech_tags = ", ".join(tags)
        primary_doc = (project_docs.get(project) or [doc_id_for(project)])[0]
        try:
            svec = ou.embed_texts([summary or proj_name])[0]
        except Exception as e:
            log.error("summary embed failed for %s: %s", proj_name, e)
            continue
        if len(svec) != config.EMBED_DIM:
            log.error("summary vector dim mismatch for %s; skipping.", proj_name)
            continue
        tracker.add_embed(_count_tokens(summary))
        _insert_rows(projects_tbl, [{
            "project": proj_name,
            "client": meta.get("client"),
            "primary_doc_id": primary_doc,
            "summary": summary,
            "tech_tags": tech_tags,
            "vector": svec,
        }], _projects_schema())
        extracted_groups[project] = proj_name
        log.info("  project '%s' tags: [%s]", proj_name, tech_tags)

    manifest["__extracted_groups__"] = extracted_groups
    save_manifest(manifest)
    G.save_graph(g)
    tracker.print_running(note="DONE")
    log.info("=== ingest complete: %d files, %d chunks, graph + tables persisted ===",
             tracker.files, tracker.chunks)
    return tracker


def main() -> None:
    ap = argparse.ArgumentParser(description="PIH ingestion pipeline")
    ap.add_argument("--full", action="store_true", help="process ALL files (default: MAX_FILES subset)")
    ap.add_argument("--max-files", type=int, default=None, help="override MAX_FILES for subset runs")
    ap.add_argument("--no-caption", action="store_true", help="skip image captioning (text only)")
    args = ap.parse_args()
    run(full=args.full, max_files=args.max_files, caption=not args.no_caption)


if __name__ == "__main__":
    main()

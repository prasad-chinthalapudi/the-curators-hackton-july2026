"""Docling-native chunking + embedding -> ONE standalone pickle of records.

Why this exists (vs the extract.py -> ingest.py Chroma path):
    The Phase-1 pickles flatten each document to (text, source_ref) strings and a
    *character* splitter re-chunks them, so a chunk that straddles a slide/page
    boundary can be mis-labelled and only a single string ref survives. Here we
    chunk the DoclingDocument directly with HybridChunker, which keeps per-chunk
    provenance (page/slide numbers + heading trail), and we also pull document
    core-properties (author, title, created/modified) for the front end.

Output: a single pickle at config.EMBED_ARTIFACT — a list[dict] where each dict is
one embedded chunk carrying rich metadata. Independent of Chroma; nothing here
touches the existing pipeline.

Run:
    python -m app.embed_docling --uploads "app/PIH - Dataset"          # subset
    python -m app.embed_docling --uploads "app/PIH - Dataset" --full   # all docs

Resumable: re-running skips documents already present in the output pickle.
"""
from __future__ import annotations

import argparse
import logging
import os
import pickle

from . import config

log = logging.getLogger("pih.embed_docling")

DEFAULT_UPLOADS = "app/PIH - Dataset"
# Docling can open these; legacy .doc needs LibreOffice and is skipped upstream.
SUPPORTED_EXTS = {".pdf", ".pptx", ".ppt", ".docx", ".md", ".markdown",
                  ".txt", ".html", ".htm", ".xlsx", ".xls", ".csv"}
# Which formats carry a page/slide number worth surfacing, and its label.
_UNIT_LABEL = {".pptx": "slide", ".ppt": "slide", ".pdf": "page"}

_converter = None
_chunker = None


# --------------------------------------------------------------------------- #
# Singletons: one Docling converter + one HybridChunker (OpenAI-token aware).
# --------------------------------------------------------------------------- #
def _get_converter():
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
    return _converter


def _get_chunker():
    global _chunker
    if _chunker is None:
        import tiktoken
        from docling.chunking import HybridChunker
        from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

        tokenizer = OpenAITokenizer(
            tokenizer=tiktoken.encoding_for_model(config.EMBED_MODEL),
            max_tokens=config.EMBED_MAX_TOKENS,
        )
        # merge_peers=True lets HybridChunker recombine undersized sibling chunks.
        _chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)
    return _chunker


# --------------------------------------------------------------------------- #
# Document-level properties (author/title/dates) for the front end.
# --------------------------------------------------------------------------- #
def _iso(dt) -> str | None:
    try:
        return dt.isoformat() if dt else None
    except Exception:
        return None


def doc_properties(path: str, ext: str) -> dict:
    """Best-effort core properties per format. Never raises."""
    props: dict = {"title": None, "author": None, "created": None,
                   "modified": None, "last_modified_by": None,
                   "subject": None, "keywords": None, "num_pages": None}
    try:
        if ext in (".pptx", ".ppt"):
            from pptx import Presentation
            pres = Presentation(path)
            cp = pres.core_properties
            props.update(title=cp.title or None, author=cp.author or None,
                         created=_iso(cp.created), modified=_iso(cp.modified),
                         last_modified_by=cp.last_modified_by or None,
                         subject=cp.subject or None, keywords=cp.keywords or None,
                         num_pages=len(pres.slides._sldIdLst))
        elif ext == ".docx":
            from docx import Document
            cp = Document(path).core_properties
            props.update(title=cp.title or None, author=cp.author or None,
                         created=_iso(cp.created), modified=_iso(cp.modified),
                         last_modified_by=cp.last_modified_by or None,
                         subject=cp.subject or None, keywords=cp.keywords or None)
        elif ext == ".pdf":
            from pypdf import PdfReader
            r = PdfReader(path)
            md = r.metadata or {}
            props.update(title=getattr(md, "title", None), author=getattr(md, "author", None),
                         created=_iso(getattr(md, "creation_date", None)),
                         modified=_iso(getattr(md, "modification_date", None)),
                         subject=getattr(md, "subject", None),
                         num_pages=len(r.pages))
        elif ext in (".xlsx", ".xls"):
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True)
            p = wb.properties
            props.update(title=p.title, author=p.creator, created=_iso(p.created),
                         modified=_iso(p.modified), last_modified_by=p.lastModifiedBy,
                         subject=p.subject, keywords=p.keywords)
            wb.close()
    except Exception as e:  # a missing/locked property must never kill a doc
        log.warning("doc_properties(%s) failed: %s", os.path.basename(path), e)
    return props


# --------------------------------------------------------------------------- #
# Chunk a single document into record dicts (no embeddings yet).
# --------------------------------------------------------------------------- #
def chunk_document(path: str) -> list[dict]:
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1].lower()
    doc = _get_converter().convert(path).document
    chunker = _get_chunker()
    props = doc_properties(path, ext)
    unit = _UNIT_LABEL.get(ext)

    records: list[dict] = []
    for i, ch in enumerate(chunker.chunk(doc)):
        pages = sorted({p.page_no for it in ch.meta.doc_items
                        for p in (it.prov or []) if p.page_no is not None})
        headings = list(ch.meta.headings or [])
        # Human-readable citation: prefer page/slide, else the heading trail.
        if pages and unit:
            span = f"{unit} {pages[0]}" if len(pages) == 1 else f"{unit}s {pages[0]}-{pages[-1]}"
            source_ref = f"{filename} · {span}"
        elif headings:
            source_ref = f"{filename} · {headings[-1]}"
        else:
            source_ref = filename
        records.append({
            "chunk_id": f"{filename}::{i}",
            "doc_id": filename,
            "doc_type": ext.lstrip("."),
            "text": ch.text,                          # raw chunk text
            "embed_text": chunker.contextualize(ch),  # heading-prefixed (what we embed)
            "embedding": None,                        # filled in embed step
            "page_nos": pages,
            "unit_label": unit,
            "headings": headings,
            "source_ref": source_ref,
            # doc-level metadata mirrored onto every chunk for easy front-end use
            "filename": filename,
            "title": props["title"],
            "author": props["author"],
            "created": props["created"],
            "modified": props["modified"],
            "last_modified_by": props["last_modified_by"],
            "subject": props["subject"],
            "keywords": props["keywords"],
            "num_pages": props["num_pages"],
        })
    return records


# --------------------------------------------------------------------------- #
# Embedding.
# --------------------------------------------------------------------------- #
_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed in batches of config.EMBED_BATCH; preserves order."""
    client = _get_client()
    out: list[list[float]] = []
    for start in range(0, len(texts), config.EMBED_BATCH):
        batch = texts[start:start + config.EMBED_BATCH]
        resp = client.embeddings.create(model=config.EMBED_MODEL, input=batch)
        out.extend(d.embedding for d in resp.data)
    return out


# --------------------------------------------------------------------------- #
# Artifact IO + driver.
# --------------------------------------------------------------------------- #
def _load_artifact(path: str) -> list[dict]:
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            log.warning("existing artifact unreadable (%s); starting fresh.", e)
    return []


def _save_artifact(records: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(records, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def iter_docs(uploads: str, subset: int | None, full: bool) -> list[str]:
    files = []
    for root, _, names in os.walk(uploads):
        for n in sorted(names):
            if os.path.splitext(n)[1].lower() in SUPPORTED_EXTS:
                files.append(os.path.join(root, n))
    files.sort()
    if not full and subset is not None:
        files = files[:subset]
    return files


def run(uploads: str = DEFAULT_UPLOADS, subset: int | None = config.MAX_FILES,
        full: bool = False, out: str = config.EMBED_ARTIFACT) -> dict:
    files = iter_docs(uploads, subset, full)
    records = _load_artifact(out)
    done_docs = {r["doc_id"] for r in records}
    log.info("embed_docling: %d candidate files (full=%s); %d docs already in artifact.",
             len(files), full, len(done_docs))

    embedded, skipped, failed = 0, 0, []
    for path in files:
        filename = os.path.basename(path)
        if filename in done_docs:
            log.info("skip (already embedded): %s", filename)
            skipped += 1
            continue
        try:
            recs = chunk_document(path)
            if not recs:
                log.warning("no chunks produced for %s", filename)
                continue
            vectors = embed_texts([r["embed_text"] for r in recs])
            for r, v in zip(recs, vectors):
                r["embedding"] = v
            records.extend(recs)
            done_docs.add(filename)
            embedded += 1
            _save_artifact(records, out)  # checkpoint after every doc
            log.info("[embedded] %s -> %d chunks (records now %d)",
                     filename, len(recs), len(records))
        except Exception as e:  # one bad doc never kills the run
            log.error("[fail] %s: %s", filename, e)
            failed.append({"path": path, "error": str(e)})

    _save_artifact(records, out)
    report = {"embedded": embedded, "skipped": skipped, "failed": len(failed),
              "failures": failed, "total_records": len(records), "artifact": out}
    log.info("=== embed_docling done: embedded=%d skipped=%d failed=%d records=%d -> %s ===",
             embedded, skipped, len(failed), len(records), out)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Docling HybridChunker + OpenAI embeddings -> single pickle of records")
    ap.add_argument("--uploads", default=DEFAULT_UPLOADS,
                    help="source directory to scan (default: %(default)s)")
    ap.add_argument("--full", action="store_true", help="process ALL docs (default: MAX_FILES)")
    ap.add_argument("--max-files", type=int, default=None, help="override MAX_FILES")
    ap.add_argument("--out", default=config.EMBED_ARTIFACT, help="output pickle path")
    args = ap.parse_args()
    subset = args.max_files if args.max_files is not None else config.MAX_FILES
    run(uploads=args.uploads, subset=subset, full=args.full, out=args.out)


if __name__ == "__main__":
    main()

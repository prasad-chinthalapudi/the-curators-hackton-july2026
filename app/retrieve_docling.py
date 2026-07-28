"""Retrieval + grounded answer over the Docling embedding artifact.

Reads the single pickle produced by app.embed_docling (chunk text + 3072-dim
OpenAI embedding + page/heading/author metadata) and serves cosine top-k search
plus a grounded LLM answer — no Chroma, no LangChain. This is the alternate
backend behind /query?backend=docling.

The artifact is loaded once and kept resident; the normalized matrix makes each
query a single matmul.
"""
from __future__ import annotations

import logging
import math
import pickle
import re

import numpy as np

from . import config

_SYSTEM = config.GROUNDED_SYSTEM_PROMPT  # shared grounded-assistant instruction

log = logging.getLogger("pih.retrieve_docling")

_records: list[dict] | None = None
_matrix: np.ndarray | None = None   # L2-normalized embeddings, shape (N, 3072)
_client = None

# --- hybrid retrieval (semantic + lexical) ---
# Rare query terms (e.g. "61", "vialto") get high IDF weight, so a chunk that
# literally contains them is boosted into the top-k even when its embedding is
# weak (poorly-extracted tables). Kept small so it nudges, never overrides, the
# semantic ranking that already works.
LEXICAL_BOOST = 0.25
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_lex_tok_sets: list[set] | None = None   # per-record token sets
_idf: dict[str, float] | None = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def _load(path: str = config.EMBED_ARTIFACT):
    """Load records + build the normalized matrix once (cached)."""
    global _records, _matrix
    if _records is None:
        with open(path, "rb") as f:
            _records = pickle.load(f)
        M = np.asarray([r["embedding"] for r in _records], dtype=np.float32)
        norms = np.linalg.norm(M, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        _matrix = M / norms
        log.info("loaded %d records (%s) from %s", len(_records), M.shape, path)
    return _records, _matrix


def _embed_query(q: str) -> np.ndarray:
    resp = _get_client().embeddings.create(model=config.EMBED_MODEL, input=[q])
    v = np.asarray(resp.data[0].embedding, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def _public(rec: dict) -> dict:
    """A record minus the heavy embedding vector — safe to return/serialize."""
    return {k: v for k, v in rec.items() if k != "embedding"}


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _build_lexical_index(records: list[dict]) -> None:
    """One-pass IDF index over chunk text + headings (cached)."""
    global _lex_tok_sets, _idf
    if _lex_tok_sets is not None:
        return
    tok_sets, df = [], {}
    for r in records:
        toks = set(_tokenize(r.get("text", "") + " " + " ".join(r.get("headings") or [])))
        tok_sets.append(toks)
        for t in toks:
            df[t] = df.get(t, 0) + 1
    n = len(records) or 1
    _idf = {t: math.log(1.0 + n / c) for t, c in df.items()}
    _lex_tok_sets = tok_sets
    log.info("built lexical index: %d records, %d terms", len(records), len(_idf))


def _lexical_scores(query: str, records: list[dict]) -> np.ndarray:
    """Per-record sum of IDF weights for query terms present, normalized to [0,1]."""
    _build_lexical_index(records)
    # Keep only meaningful terms (drop high-frequency stopwords via an IDF floor),
    # so the boost is driven by rare, discriminating tokens.
    qterms = {t for t in _tokenize(query) if _idf.get(t, 0.0) >= 1.5}
    raw = np.zeros(len(records), dtype=np.float32)
    if not qterms:
        return raw
    for i, toks in enumerate(_lex_tok_sets):
        hit = qterms & toks
        if hit:
            raw[i] = sum(_idf.get(t, 0.0) for t in hit)
    m = float(raw.max())
    return raw / m if m > 0 else raw


def _passes(rec: dict, filters: dict) -> bool:
    """Front-end filter predicate. Multi-valued filters are OR within a facet,
    AND across facets. Year uses an inclusive [from, to] range."""
    dt = filters.get("doc_types")
    if dt and rec.get("doc_type") not in dt:
        return False
    want_tech = filters.get("technologies")
    if want_tech and not (set(want_tech) & set(rec.get("technologies") or [])):
        return False
    want_ind = filters.get("industries")
    if want_ind and not (set(want_ind) & set(rec.get("industries") or [])):
        return False
    yr = rec.get("year")
    if filters.get("year_from") is not None and (yr is None or yr < filters["year_from"]):
        return False
    if filters.get("year_to") is not None and (yr is None or yr > filters["year_to"]):
        return False
    return True


def search(query: str, k: int = config.TOP_K, filters: dict | None = None) -> list[dict]:
    """Cosine top-k, optionally restricted to records passing `filters`.
    Returns records (sans embedding) with a `score` field."""
    records, M = _load()
    q = _embed_query(query)
    scores = M @ q                      # cosine, since both sides are normalized
    scores = scores + LEXICAL_BOOST * _lexical_scores(query, records)  # hybrid boost

    if filters:
        mask = np.array([_passes(r, filters) for r in records])
        if not mask.any():
            return []
        scores = np.where(mask, scores, -np.inf)

    k = max(1, min(k, len(records)))
    idx = np.argpartition(-scores, k - 1)[:k]
    idx = idx[np.argsort(-scores[idx])]  # order the k by descending score
    hits = []
    for i in idx:
        if scores[int(i)] == -np.inf:    # fewer matches than k
            break
        rec = _public(records[int(i)])
        rec["score"] = float(scores[int(i)])
        hits.append(rec)
    return hits


def facets() -> dict:
    """Distinct filter values (with doc counts) for the front-end filter panel.
    Counts are per-document, not per-chunk."""
    records, _ = _load()
    seen: dict[str, dict] = {}
    for r in records:
        if r["doc_id"] not in seen:
            seen[r["doc_id"]] = r
    from collections import Counter
    doc_types, techs, inds, years = Counter(), Counter(), Counter(), Counter()
    for r in seen.values():
        doc_types[r.get("doc_type")] += 1
        for t in r.get("technologies") or []:
            techs[t] += 1
        for i in r.get("industries") or []:
            inds[i] += 1
        if r.get("year") is not None:
            years[r["year"]] += 1
    yrs = sorted(years)
    return {
        "doc_types": dict(doc_types),
        "technologies": dict(techs),
        "industries": dict(inds),
        "years": dict(sorted(years.items())),
        "year_min": yrs[0] if yrs else None,
        "year_max": yrs[-1] if yrs else None,
        "total_documents": len(seen),
    }


def _format_context(hits: list[dict]) -> str:
    return "\n\n".join(f"[{h['source_ref']}]\n{h['text']}" for h in hits)


def answer_query(question: str, k: int = config.TOP_K, filters: dict | None = None) -> dict:
    """Retrieve + generate a grounded answer. Never raises.
    Returns {answer, sources, contexts} — same shape as rag.answer_query, plus
    `sources` carries per-hit front-end metadata (page_nos, author, ...)."""
    try:
        hits = search(question, k=k, filters=filters)
        if not hits:
            return {"answer": "No indexed documents match the selected filters.",
                    "sources": [], "contexts": []}
    except FileNotFoundError:
        return {"answer": "The Docling embedding artifact was not found — run "
                          "`python -m app.embed_docling --full` first.",
                "sources": [], "contexts": []}
    except Exception as e:
        log.error("docling search failed: %s", e)
        return {"answer": "Retrieval over the Docling artifact hit an error.",
                "sources": [], "contexts": []}

    try:
        client = _get_client()
        model = config.resolve_model(config.GEN_MODEL_PRIMARY, config.GEN_MODEL_FALLBACK)
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Context:\n{_format_context(hits)}\n\nQuestion: {question}"},
        ]
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, temperature=config.TEMPERATURE)
        except Exception:  # some models reject a non-default temperature
            resp = client.chat.completions.create(model=model, messages=messages)
        answer = resp.choices[0].message.content or ""
    except Exception as e:
        log.error("docling generation failed: %s", e)
        answer = "The query pipeline hit an error and could not produce an answer."

    # De-dup sources by source_ref, preserving order; carry front-end metadata.
    seen, sources = set(), []
    for h in hits:
        ref = h["source_ref"]
        if ref in seen:
            continue
        seen.add(ref)
        sources.append({
            "source_ref": ref, "doc_id": h["doc_id"], "doc_type": h["doc_type"],
            "page_nos": h["page_nos"], "headings": h["headings"],
            "title": h["title"], "author": h["author"],
            "created": h["created"], "modified": h["modified"],
            "score": h["score"],
            # enrichment fields (present once app.enrich_metadata has run)
            "technologies": h.get("technologies", []),
            "industries": h.get("industries", []),
            "year": h.get("year"),
            "poc_name": h.get("poc_name"),
            "poc_email": h.get("poc_email"),
            "contact_emails": h.get("contact_emails", []),
        })
    return {"answer": answer, "sources": sources,
            "contexts": [h["text"] for h in hits]}


# --------------------------------------------------------------------------- #
# Document-level helpers (read-only over the resident records) — used by the
# /api adapter and the one-pager generator.
# --------------------------------------------------------------------------- #
_by_doc: dict[str, list[dict]] | None = None


def records_by_doc(path: str = config.EMBED_ARTIFACT) -> dict[str, list[dict]]:
    """doc_id -> its chunk records (chunk order preserved). Cached; sans-embedding
    view so callers never touch the vectors."""
    global _by_doc
    if _by_doc is None:
        records, _ = _load(path)
        grouped: dict[str, list[dict]] = {}
        for r in records:
            grouped.setdefault(r["doc_id"], []).append(_public(r))
        _by_doc = grouped
    return _by_doc


def get_document(doc_id: str) -> list[dict]:
    """All chunk records for one document (empty list if unknown)."""
    return records_by_doc().get(doc_id, [])


def document_meta(doc_id: str) -> dict:
    """Doc-level metadata (from the first chunk) for building search results /
    one-pager sources. Empty dict if the doc is unknown."""
    recs = get_document(doc_id)
    if not recs:
        return {}
    r0 = recs[0]
    return {
        "doc_id": doc_id,
        "filename": r0.get("filename", doc_id),
        "doc_type": r0.get("doc_type"),
        "title": r0.get("title"),
        "author": r0.get("author"),
        "created": r0.get("created"),
        "modified": r0.get("modified"),
        "year": r0.get("year"),
        "technologies": r0.get("technologies", []),
        "industries": r0.get("industries", []),
        "poc_name": r0.get("poc_name"),
        "poc_email": r0.get("poc_email"),
        "contact_emails": r0.get("contact_emails", []),
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Search the Docling embedding artifact")
    ap.add_argument("query", help="question / search text")
    ap.add_argument("-k", type=int, default=config.TOP_K)
    ap.add_argument("--no-answer", action="store_true", help="retrieval only, skip the LLM")
    args = ap.parse_args()
    if args.no_answer:
        for h in search(args.query, k=args.k):
            pages = ",".join(map(str, h["page_nos"])) or "-"
            print(f"[{h['score']:.3f}] {h['source_ref']}  (author={h['author']}, pages={pages})")
            print(f"    {h['text'][:160].strip()}")
    else:
        out = answer_query(args.query, k=args.k)
        print("ANSWER:\n", out["answer"], "\n\nSOURCES:")
        for s in out["sources"]:
            print(f"  - {s['source_ref']}  (score={s['score']:.3f}, author={s['author']})")


if __name__ == "__main__":
    main()

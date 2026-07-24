"""Phase 2 — Indexing. Read the pickles produced by Phase 1 (app.extract),
chunk -> embed -> Chroma. Re-chunking never re-parses (that's the whole point of
the two-phase split). Resumable via the manifest's per-file `indexed` flag.

Run (after `python -m app.extract`):
    python -m app.ingest            # index everything extracted (subset-aware)
    python -m app.ingest --full     # index all extracted pickles
"""
from __future__ import annotations

import argparse
import logging
import os

from langchain_core.documents import Document

from . import common, config
from .artifacts import ExtractedDoc, load_extracted

log = logging.getLogger("pih.ingest")

_vectorstore = None
_splitter = None


def get_vectorstore():
    """LangChain Chroma store; persistence to CHROMA_DIR is automatic."""
    global _vectorstore
    if _vectorstore is None:
        from langchain_chroma import Chroma
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(model=config.EMBED_MODEL, api_key=config.OPENAI_API_KEY)
        os.makedirs(config.CHROMA_DIR, exist_ok=True)
        _vectorstore = Chroma(
            persist_directory=config.CHROMA_DIR,
            embedding_function=embeddings,
            collection_name=config.CHROMA_COLLECTION,
        )
    return _vectorstore


def _get_splitter():
    global _splitter
    if _splitter is None:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        _splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=config.CHUNK_TOKENS, chunk_overlap=config.CHUNK_OVERLAP
        )
    return _splitter


def documents_from_extracted(ed: ExtractedDoc) -> list[Document]:
    """Build LangChain Documents (one per extracted unit) with FLAT metadata.
    Splitting into chunks happens after this in run_ingest."""
    docs = []
    for unit in ed.units:
        meta = {
            "doc_id": ed.doc_id,
            "project_id": ed.project_id,
            "source_ref": unit.source_ref,
            "doc_type": ed.doc_type,
        }
        meta.update(ed.metadata)  # {} in v1; must stay flat for Chroma where-filters
        docs.append(Document(page_content=unit.text, metadata=meta))
    return docs


def _delete_existing(vs, doc_id: str) -> None:
    """Drop any prior chunks for this doc_id so a re-index doesn't duplicate."""
    try:
        existing = vs.get(where={"doc_id": doc_id})
        ids = existing.get("ids") or []
        if ids:
            vs.delete(ids=ids)
    except Exception as e:
        log.warning("delete existing chunks for %s failed (%s) - continuing.", doc_id, e)


def _index_pickle(vs, splitter, pickle_path: str) -> int:
    ed = load_extracted(pickle_path)
    docs = documents_from_extracted(ed)
    if not docs:
        return 0
    chunks = splitter.split_documents(docs)
    _delete_existing(vs, ed.doc_id)
    vs.add_documents(chunks)  # persists automatically
    return len(chunks)


def run_ingest(subset: int | None = config.MAX_FILES, full: bool = False) -> dict:
    manifest = common.load_manifest()
    vs = get_vectorstore()
    splitter = _get_splitter()

    # Drive off the manifest (ties the two phases together). Fall back to scanning
    # EXTRACTED_DIR if there's no manifest (e.g. pickles copied in from elsewhere).
    candidates: list[tuple[str, str]] = []  # (source_path, pickle_path)
    if manifest:
        for path, entry in manifest.items():
            if entry.get("extracted") and entry.get("pickle") and os.path.exists(entry["pickle"]):
                candidates.append((path, entry["pickle"]))
    else:
        if os.path.isdir(config.EXTRACTED_DIR):
            for fn in sorted(os.listdir(config.EXTRACTED_DIR)):
                if fn.endswith(".pkl"):
                    candidates.append((fn, os.path.join(config.EXTRACTED_DIR, fn)))

    candidates.sort()
    if not full and subset is not None:
        candidates = candidates[:subset]
    log.info("index: %d extracted pickles to consider (full=%s)", len(candidates), full)
    if not candidates:
        log.warning("nothing to index — run `python -m app.extract` first.")

    indexed, skipped, failed = 0, 0, []
    total_chunks = 0
    for path, pk in candidates:
        entry = manifest.get(path, {})
        if entry.get("indexed") and entry.get("index_pickle") == pk:
            log.info("skip (already indexed): %s", os.path.basename(path))
            skipped += 1
            continue
        try:
            n = _index_pickle(vs, splitter, pk)
            total_chunks += n
            indexed += 1
            if path in manifest:
                manifest[path]["indexed"] = True
                manifest[path]["index_pickle"] = pk
                manifest[path]["chunks"] = n
                common.save_manifest(manifest)
            log.info("[indexed] %s -> %d chunks (running total %d)",
                     os.path.basename(path), n, total_chunks)
        except Exception as e:
            log.error("[fail] index %s: %s", os.path.basename(path), e)
            failed.append({"pickle": pk, "error": str(e)})

    report = {"indexed": indexed, "skipped": skipped, "failed": len(failed),
              "failures": failed, "chunks": total_chunks}
    log.info("=== index done: indexed=%d skipped=%d failed=%d chunks=%d ===",
             indexed, skipped, len(failed), total_chunks)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="PIH Phase 2 — index pickles into Chroma")
    ap.add_argument("--full", action="store_true", help="index ALL extracted pickles")
    ap.add_argument("--max-files", type=int, default=None, help="override MAX_FILES")
    args = ap.parse_args()
    subset = args.max_files if args.max_files is not None else config.MAX_FILES
    run_ingest(subset=subset, full=args.full)


if __name__ == "__main__":
    main()

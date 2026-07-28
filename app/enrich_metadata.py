"""Enrich docling_records.pkl with front-end filter metadata via one LLM call/doc.

Adds, to every chunk record of a document (doc-level fields mirrored per chunk):
    technologies   : subset of TECHNOLOGIES (semantic, LLM-inferred)
    industries     : subset of INDUSTRIES   (semantic, LLM-inferred)
    year           : int|None  (deterministic, from the doc's created/modified date)
    poc_name       : str|None  (project point-of-contact / lead / presenter / author)
    poc_email      : str|None
    contact_emails : list[str] (LLM ∪ regex over the doc text)
    enriched       : True

Does NOT re-embed — operates on the text already in the artifact. Resumable:
re-running skips documents whose records are already `enriched`.

Run:
    python -m app.enrich_metadata                 # subset (MAX_FILES docs)
    python -m app.enrich_metadata --full          # all docs in the artifact
"""
from __future__ import annotations

import argparse
import json
import logging
import re

from . import config

log = logging.getLogger("pih.enrich")

# Canonical filter taxonomies (match the front-end filter panel; extend freely).
TECHNOLOGIES = ["Azure", "Snowflake", "Databricks", "ADF", "AWS",
                "Power BI", "Python", "Machine Learning", "GenAI"]
INDUSTRIES = ["Healthcare", "Retail", "Travel", "Insurance", "Banking", "Hospitality"]

MAX_DOC_CHARS = 18000          # cap text sent to the LLM per doc (cost control)
CHECKPOINT_EVERY = 20          # save the pickle every N enriched docs

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


_SYSTEM = (
    "You extract structured metadata from a business case-study / project document. "
    "Return ONLY a JSON object, no prose. Be precise and do not invent contacts or "
    "emails that are not supported by the text."
)


def _prompt(doc_text: str, author: str | None) -> str:
    return (
        "From the DOCUMENT below, extract this JSON object:\n"
        "{\n"
        '  "technologies": [],   // ONLY values from this set, with clear evidence: '
        f"{TECHNOLOGIES}\n"
        '  "industries": [],     // ONLY values from this set; pick the client\'s sector '
        "even if not named literally (e.g. American Express -> Banking): "
        f"{INDUSTRIES}\n"
        '  "poc_name": null,     // project point-of-contact / lead / presenter / prepared-by; '
        "else the document author if that clearly identifies a person\n"
        '  "poc_email": null,    // that person\'s email if it appears in the text\n'
        '  "contact_emails": []  // every email address literally present in the text\n'
        "}\n"
        "Rules: use [] / null when unknown. Never output a value outside the allowed sets. "
        "Return strictly valid JSON.\n\n"
        f"Document author (from file properties, may be a person or blank): {author or 'unknown'}\n\n"
        f"DOCUMENT:\n{doc_text}"
    )


def _clean_list(values, allowed: list[str]) -> list[str]:
    """Keep only allowed canonical values, case-insensitively, order-preserving."""
    idx = {a.lower(): a for a in allowed}
    out, seen = [], set()
    for v in values or []:
        canon = idx.get(str(v).strip().lower())
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def extract_for_doc(doc_text: str, author: str | None) -> dict:
    """One LLM call -> validated metadata dict. Raises on hard API failure."""
    client = _get_client()
    model = config.resolve_model(config.GEN_MODEL_PRIMARY, config.GEN_MODEL_FALLBACK)
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _prompt(doc_text[:MAX_DOC_CHARS], author)}]
    kwargs = dict(model=model, messages=messages,
                  response_format={"type": "json_object"})
    try:
        resp = client.chat.completions.create(temperature=0, **kwargs)
    except Exception:
        try:  # some models reject temperature and/or response_format
            resp = client.chat.completions.create(**kwargs)
        except Exception:
            resp = client.chat.completions.create(model=model, messages=messages)
    raw = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except Exception:  # salvage a JSON object embedded in stray text
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
    return {
        "technologies": _clean_list(data.get("technologies"), TECHNOLOGIES),
        "industries": _clean_list(data.get("industries"), INDUSTRIES),
        "poc_name": (data.get("poc_name") or None),
        "poc_email": (data.get("poc_email") or None),
        "contact_emails": [e for e in (data.get("contact_emails") or []) if _EMAIL_RE.fullmatch(str(e))],
    }


def _year_of(rec: dict) -> int | None:
    # Prefer `modified`: PPTX/DOCX `created` is often the template's ancient date
    # (135/829 docs here show a 3+ yr created→modified gap), so it misleads the
    # Year filter. `modified` tracks when the deck was actually produced.
    for key in ("modified", "created"):
        val = rec.get(key)
        if isinstance(val, str) and len(val) >= 4 and val[:4].isdigit():
            return int(val[:4])
    return None


def run(subset: int | None = config.MAX_FILES, full: bool = False,
        path: str = config.EMBED_ARTIFACT) -> dict:
    import os
    import pickle

    with open(path, "rb") as f:
        records: list[dict] = pickle.load(f)

    # Group record indices by document, preserving first-seen order.
    by_doc: dict[str, list[int]] = {}
    for i, r in enumerate(records):
        by_doc.setdefault(r["doc_id"], []).append(i)

    doc_ids = list(by_doc.keys())
    if not full and subset is not None:
        doc_ids = doc_ids[:subset]

    def _save():
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            pickle.dump(records, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)

    enriched, skipped, failed = 0, 0, []
    for n, doc_id in enumerate(doc_ids, start=1):
        idxs = by_doc[doc_id]
        if all(records[i].get("enriched") for i in idxs):
            skipped += 1
            continue
        # Build the doc text from its chunks (deterministic email regex over full text).
        doc_text = "\n\n".join(records[i]["text"] for i in idxs)
        emails_regex = sorted(set(_EMAIL_RE.findall(doc_text)))
        author = records[idxs[0]].get("author")
        year = _year_of(records[idxs[0]])
        try:
            meta = extract_for_doc(doc_text, author)
        except Exception as e:
            log.error("[fail] %s: %s", doc_id, e)
            failed.append({"doc_id": doc_id, "error": str(e)})
            continue

        contacts = sorted(set(meta["contact_emails"]) | set(emails_regex))
        for i in idxs:
            records[i].update(
                technologies=meta["technologies"], industries=meta["industries"],
                year=year, poc_name=meta["poc_name"],
                poc_email=meta["poc_email"], contact_emails=contacts,
                enriched=True,
            )
        enriched += 1
        log.info("[enriched] %s -> tech=%s industry=%s poc=%s emails=%d",
                 doc_id, meta["technologies"], meta["industries"],
                 meta["poc_name"], len(contacts))
        if enriched % CHECKPOINT_EVERY == 0:
            _save()

    _save()
    report = {"enriched": enriched, "skipped": skipped, "failed": len(failed),
              "failures": failed, "docs": len(doc_ids)}
    log.info("=== enrich done: enriched=%d skipped=%d failed=%d ===",
             enriched, skipped, len(failed))
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="LLM-enrich docling_records.pkl with filter metadata")
    ap.add_argument("--full", action="store_true", help="enrich ALL docs in the artifact")
    ap.add_argument("--max-files", type=int, default=None, help="override MAX_FILES (doc count)")
    ap.add_argument("--path", default=config.EMBED_ARTIFACT, help="artifact pickle path")
    args = ap.parse_args()
    subset = args.max_files if args.max_files is not None else config.MAX_FILES
    run(subset=subset, full=args.full, path=args.path)


if __name__ == "__main__":
    main()

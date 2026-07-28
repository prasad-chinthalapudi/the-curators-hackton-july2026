"""Final PIH hackathon submission helpers.

Two subcommands, both reusing modules already built:
  answers  — fill every `answer` field in the evaluation JSON with the app's full
             grounded RAG answer (with [source_ref] citations), via
             retrieve_docling.answer_query.
  brief    — generate the required "NCL Snowflake ML Modernization" one-page sales
             brief PDF via onepager.generate_one_pager, copied to submission/.

Runs offline against data/embeddings/docling_records.pkl (no server needed);
requires OPENAI_API_KEY in the repo-root .env.

    python -m app.submission answers --in questions.json --out questions_answered.json
    python -m app.submission brief
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil

from . import config, onepager
from . import retrieve_docling as rd

log = logging.getLogger("pih.submission")

DEFAULT_IN = "questions.json"
DEFAULT_OUT = "questions_answered.json"
DEFAULT_BRIEF_TITLE = "NCL Snowflake ML Modernization"
DEFAULT_BRIEF_OUT = "submission/NCL_Snowflake_ML_Modernization_Sales_Brief.pdf"


# --------------------------------------------------------------------------- #
# answers
# --------------------------------------------------------------------------- #
def fill_answers(in_path: str, out_path: str, k: int) -> dict:
    with open(in_path, encoding="utf-8") as f:
        data = json.load(f)
    # The portal schema uses "answers"; the earlier example used "questions". Support both.
    array_key = "answers" if isinstance(data.get("answers"), list) else "questions"
    questions = data.get(array_key, [])
    log.info("answering %d items (key=%r) from %s", len(questions), array_key, in_path)

    for i, q in enumerate(questions, start=1):
        text = (q.get("question") or "").strip()
        num = q.get("question_number", i)
        if not text:
            log.warning("Q%s has no question text; skipping.", num)
            q["answer"] = ""
            continue
        try:
            out = rd.answer_query(text, k=k)
            q["answer"] = (out.get("answer") or "").strip()
        except Exception as e:  # one bad question never aborts the run
            log.error("Q%s failed: %s", num, e)
            q["answer"] = f"[ERROR: could not generate an answer ({e})]"
        log.info("Q%s answered (%d chars)", num, len(q["answer"]))

    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)
    filled = sum(1 for q in questions if (q.get("answer") or "").strip())
    log.info("=== wrote %s (%d/%d answered) ===", out_path, filled, len(questions))
    return {"total": len(questions), "answered": filled, "out": out_path}


# --------------------------------------------------------------------------- #
# brief
# --------------------------------------------------------------------------- #
def _ncl_doc_ids(explicit: list[str] | None) -> list[str]:
    """Explicit --docs if given, else every indexed doc whose filename mentions NCL."""
    if explicit:
        return explicit
    by_doc = rd.records_by_doc()
    return sorted(d for d in by_doc if "ncl" in d.lower())


def make_brief(title: str, docs: list[str] | None, out_path: str) -> dict:
    doc_ids = _ncl_doc_ids(docs)
    if not doc_ids:
        raise SystemExit("no NCL documents found in the index — pass --docs explicitly.")
    log.info("brief '%s' from %d source doc(s): %s", title, len(doc_ids), doc_ids)
    result = onepager.generate_one_pager(doc_ids, title=title)
    pdf = onepager.one_pager_pdf_path(result["one_pager_id"])
    if not pdf:
        raise SystemExit("PDF was not produced — check reportlab install / logs.")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    shutil.copyfile(pdf, out_path)
    log.info("=== brief %s -> %s ===", result["one_pager_id"], out_path)
    return {"title": result["title"], "one_pager_id": result["one_pager_id"],
            "sources": doc_ids, "pdf": out_path}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="PIH final submission helpers")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("answers", help="fill the evaluation JSON with grounded answers")
    a.add_argument("--in", dest="in_path", default=DEFAULT_IN, help="input questions JSON")
    a.add_argument("--out", dest="out_path", default=DEFAULT_OUT, help="output JSON")
    a.add_argument("-k", type=int, default=max(8, config.TOP_K), help="retrieval top-k")

    b = sub.add_parser("brief", help="generate the NCL sales-brief PDF")
    b.add_argument("--title", default=DEFAULT_BRIEF_TITLE)
    b.add_argument("--docs", nargs="*", default=None,
                   help="explicit source doc_ids (default: all NCL-named docs)")
    b.add_argument("--out", dest="out_path", default=DEFAULT_BRIEF_OUT)

    args = ap.parse_args()
    if args.cmd == "answers":
        if not os.path.exists(args.in_path):
            raise SystemExit(f"input not found: {args.in_path} — drop the questions JSON there.")
        r = fill_answers(args.in_path, args.out_path, args.k)
        print(f"Answered {r['answered']}/{r['total']} -> {r['out']}")
    elif args.cmd == "brief":
        r = make_brief(args.title, args.docs, args.out_path)
        print(f"Title: {r['title']}\nSources: {len(r['sources'])} docs\nPDF: {r['pdf']}")


if __name__ == "__main__":
    main()

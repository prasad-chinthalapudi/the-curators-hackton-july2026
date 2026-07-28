"""Sales-brief one-pager generation — the required PIH hackathon artifact.

Implements the supplied `participant_sales_brief_generation_prompt.md` template:
its Goal / Audience / Hard-rules / Required-structure / Writing-style are preserved
verbatim; only the "Final output format" is adapted to emit strict JSON whose keys
match the frontend `OnePager` type, so the web view and the PDF share one source of
truth. Everything is grounded ONLY in the selected documents' extracted text.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime

from . import config
from . import retrieve_docling as rd

log = logging.getLogger("pih.onepager")

# --------------------------------------------------------------------------- #
# The prompt template (rules verbatim from the supplied spec; output = JSON).
# --------------------------------------------------------------------------- #
SALES_BRIEF_SYSTEM = (
    "You are generating the required PIH Hackathon project one-pager / sales brief. "
    "You write a polished, shareable, one-page sales brief for ONE project, generated "
    "strictly from the provided source materials — never from imagination or a generic "
    "template. Audience: Blend360 sales, delivery, and account teams who need to quickly "
    "understand a past project and reuse it as a credible capability story.\n\n"
    "HARD RULES:\n"
    "1. Use only facts supported by the provided materials.\n"
    "2. Do not invent client names, dates, technologies, metrics, outcomes, team roles, "
    "project owners, or business impact.\n"
    "3. If a required section is not supported, add a short 'Known gap' note for it "
    "instead of guessing.\n"
    "4. Read like a short case study / sales brief, not raw notes.\n"
    "5. Concise enough to fit one page.\n"
    "6. Make the value clear for a sales or delivery reader.\n"
    "7. Prefer specific, quantified outcomes when the source supports them.\n"
    "8. Reference sources for important claims (metrics, technologies, client/project "
    "names, outcomes).\n"
    "9. If evidence conflicts, prefer the most final/current material and note the "
    "conflict briefly under known gaps.\n"
    "10. Output must be usable as a hackathon submission artifact.\n\n"
    "Writing style: clear, executive, business-facing; no hype without evidence; short "
    "paragraphs and scannable bullets; do not repeat 'based on the provided materials'."
)

# The output-format instruction (replaces the template's Markdown block with JSON).
_JSON_INSTRUCTION = (
    "Return ONLY a JSON object with EXACTLY these keys (no markdown, no prose outside "
    "JSON):\n"
    "{\n"
    '  "title": string,             // project name + short descriptor, '
    'e.g. "ML Model Workflows in Snowflake - Norwegian Cruise Line"\n'
    '  "case_study_line": string,   // one line identifying it as a Blend360 case study\n'
    '  "executive_summary": string, // 1-2 short paragraphs: who was helped, the '
    'problem, what was delivered, headline outcomes\n'
    '  "challenge": string,         // the situation before the work\n'
    '  "solution": string,          // what Blend360 built/delivered + tech stack + '
    'delivery model if supported\n'
    '  "key_features": [string],    // 3-5 items, each "Feature Name - one sentence"\n'
    '  "quantified_outcomes": [string], // sourced metrics only; if none, a single '
    'item: "Known gap: the provided materials do not include quantified outcomes."\n'
    '  "business_value": string,    // why it matters in a sales conversation\n'
    '  "known_gaps": [string],      // missing info; for each: what is missing, who to '
    'ask, how it would improve the brief\n'
    '  "sources_used": [string]     // specific source references (file, slide/page) '
    'for important claims\n'
    "}\n"
    "Use [] / empty string only where the materials truly do not support content."
)


def _get_client():
    return rd._get_client()  # reuse the singleton OpenAI client


# --------------------------------------------------------------------------- #
# Source gathering.
# --------------------------------------------------------------------------- #
def gather_source_materials(doc_ids: list[str]) -> tuple[str, list[dict]]:
    """Build the 'Source materials' block from the selected docs' chunks, and the
    structured {document_id, file_name} list. Returns ('' , []) if nothing found."""
    blocks: list[str] = []
    sources: list[dict] = []
    for doc_id in doc_ids:
        recs = rd.get_document(doc_id)
        if not recs:
            continue
        fname = recs[0].get("filename", doc_id)
        sources.append({"document_id": doc_id, "file_name": fname})
        blocks.append(f"### FILE: {fname}")
        for r in recs:
            pages = r.get("page_nos") or []
            ref = ("slide/page " + ", ".join(map(str, pages))) if pages else "n/a"
            heading = " / ".join(r.get("headings") or [])
            head = f" [{heading}]" if heading else ""
            blocks.append(f"({ref}){head} {r.get('text', '').strip()}")
    text = "\n".join(blocks)
    if len(text) > config.ONEPAGER_MAX_SOURCE_CHARS:
        text = text[: config.ONEPAGER_MAX_SOURCE_CHARS] + "\n…[truncated]"
    return text, sources


def _project_name_hint(doc_ids: list[str], title: str | None) -> str:
    if title:
        return title
    for doc_id in doc_ids:
        meta = rd.document_meta(doc_id)
        if meta:
            return meta.get("filename", doc_id)
    return doc_ids[0] if doc_ids else "Unknown Project"


def _chat_json(system: str, user: str) -> dict:
    """One JSON-mode chat call with graceful fallbacks; returns a parsed dict."""
    client = _get_client()
    model = config.resolve_model(config.GEN_MODEL_PRIMARY, config.GEN_MODEL_FALLBACK)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    kwargs = dict(model=model, messages=messages, response_format={"type": "json_object"})
    try:
        resp = client.chat.completions.create(temperature=0, **kwargs)
    except Exception:
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception:
            resp = client.chat.completions.create(model=model, messages=messages)
    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group(0)) if m else {}


# --------------------------------------------------------------------------- #
# Generation.
# --------------------------------------------------------------------------- #
def _as_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []


def generate_one_pager(doc_ids: list[str], title: str | None = None) -> dict:
    """Generate + persist a sales brief. Returns an OnePager-shaped dict.
    Raises ValueError if none of the doc_ids resolve to indexed content."""
    materials, sources = gather_source_materials(doc_ids)
    if not materials:
        raise ValueError("none of the selected document_ids are in the index")

    project = _project_name_hint(doc_ids, title)
    user = (f"Project to brief: {project}\n\n"
            f"{_JSON_INSTRUCTION}\n\n"
            f"SOURCE MATERIALS:\n{materials}")
    data = _chat_json(SALES_BRIEF_SYSTEM, user)

    one_pager_id = uuid.uuid4().hex[:12]
    generated_date = datetime.now().strftime("%B %d, %Y")
    # Prefer the true file list as sources_used (frontend renders {document_id, file_name}).
    result = {
        "one_pager_id": one_pager_id,
        "title": str(data.get("title") or f"{project} - Sales Brief"),
        "generated_date": generated_date,
        "case_study_line": str(data.get("case_study_line")
                               or f"{project} - A Blend360 Case Study"),
        "executive_summary": str(data.get("executive_summary") or ""),
        "challenge": str(data.get("challenge") or ""),
        "solution": str(data.get("solution") or ""),
        "key_features": _as_list(data.get("key_features")),
        "quantified_outcomes": _as_list(data.get("quantified_outcomes"))
            or ["Known gap: the provided materials do not include quantified outcomes."],
        "business_value": str(data.get("business_value") or ""),
        "known_gaps": _as_list(data.get("known_gaps")),
        "sources_used": sources,
        # kept for the PDF only (richer slide-level lines from the LLM); not in the TS type
        "_source_lines": _as_list(data.get("sources_used")),
    }
    _persist(result)
    log.info("generated one-pager %s (%d docs) -> %s", one_pager_id, len(sources), project)
    return result


# --------------------------------------------------------------------------- #
# Readiness / coverage.
# --------------------------------------------------------------------------- #
from .api_schemas import COVERAGE_FIELDS  # noqa: E402  (avoid a cycle at import top)

_COVERAGE_LABELS = {
    "executive_summary": "Executive Summary", "challenge": "Challenge",
    "solution": "Solution", "technology_stack": "Technology Stack",
    "business_outcome": "Business Outcome", "metrics": "Metrics",
    "delivery_team": "Delivery Team", "lessons_learned": "Lessons Learned",
}


def assess_readiness(doc_ids: list[str]) -> dict:
    """Classify each of the 8 brief sections available|partial|missing over the
    selected docs, and list gaps. Returns a Readiness-shaped dict."""
    materials, sources = gather_source_materials(doc_ids)
    n = len(sources)
    if not materials:
        cov = {f: "missing" for f in COVERAGE_FIELDS}
        return {"status": "needs_input", "selected_document_count": 0,
                "coverage": cov,
                "gaps": [{"field": f, "label": _COVERAGE_LABELS[f], "status": "missing",
                          "message": "No indexed content for the selected documents."}
                         for f in COVERAGE_FIELDS]}

    instruction = (
        "Assess whether the SOURCE MATERIALS support each section of a sales brief. "
        "Return ONLY JSON: {\"coverage\": {<field>: \"available\"|\"partial\"|\"missing\"}, "
        "\"gaps\": [{\"field\": <field>, \"message\": <what is missing / who to ask>}]}. "
        f"Fields (use these exact keys): {COVERAGE_FIELDS}. "
        "available = clearly supported; partial = hinted but thin; missing = absent."
    )
    data = _chat_json(
        "You evaluate whether project source materials can support each section of a "
        "Blend360 sales brief. Be strict and only mark 'available' with clear evidence.",
        f"{instruction}\n\nSOURCE MATERIALS:\n{materials}")

    raw_cov = data.get("coverage") or {}
    cov = {}
    for f in COVERAGE_FIELDS:
        v = str(raw_cov.get(f, "missing")).lower()
        cov[f] = v if v in ("available", "partial", "missing") else "missing"

    gap_msgs = {g.get("field"): g.get("message", "") for g in (data.get("gaps") or [])
                if isinstance(g, dict)}
    gaps = [{"field": f, "label": _COVERAGE_LABELS[f], "status": cov[f],
             "message": gap_msgs.get(f) or f"{_COVERAGE_LABELS[f]} is not well covered."}
            for f in COVERAGE_FIELDS if cov[f] != "available"]

    available = sum(1 for v in cov.values() if v == "available")
    status = ("ready" if available >= 6 else "partial" if available >= 3 else "needs_input")
    return {"status": status, "selected_document_count": n, "coverage": cov, "gaps": gaps}


# --------------------------------------------------------------------------- #
# Persistence.
# --------------------------------------------------------------------------- #
def _persist(one_pager: dict) -> None:
    os.makedirs(config.ONEPAGER_DIR, exist_ok=True)
    path = os.path.join(config.ONEPAGER_DIR, f"{one_pager['one_pager_id']}.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(one_pager, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    # Render + cache the PDF next to the JSON.
    try:
        from .pdf_render import render_pdf
        pdf_bytes = render_pdf(one_pager)
        with open(os.path.join(config.ONEPAGER_DIR, f"{one_pager['one_pager_id']}.pdf"), "wb") as f:
            f.write(pdf_bytes)
    except Exception as e:
        log.error("PDF render failed for %s: %s", one_pager["one_pager_id"], e)


def load_one_pager(one_pager_id: str) -> dict | None:
    path = os.path.join(config.ONEPAGER_DIR, f"{one_pager_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def one_pager_pdf_path(one_pager_id: str) -> str | None:
    path = os.path.join(config.ONEPAGER_DIR, f"{one_pager_id}.pdf")
    return path if os.path.exists(path) else None

import logging
import os
import re
from datetime import date
from pathlib import Path
from uuid import uuid4

from langchain_openai import ChatOpenAI

from app.core.settings import Settings, settings
from app.ingestion.index_loader import load_pilot_documents
from app.retrieval.retriever import RetrievedChunk, retrieve_chunks
from app.services.store import read_json, write_json

log = logging.getLogger("pih.one_pager")
PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "prompts"
    / "participant_sales_brief_generation_prompt.md"
)
# The source attachment ends with one additional newline. Appending it here
# makes the runtime prompt byte-for-byte equivalent without editing its text.
ONE_PAGER_PROMPT = PROMPT_PATH.read_text(encoding="utf-8") + "\n"

SECTION_NAMES = (
    "Executive Summary",
    "The Challenge",
    "Our Solution",
    "Key Features",
    "Quantified Outcomes",
    "Business Value",
    "Known Gaps / Caveats",
    "Sources Used",
)

COVERAGE_TERMS = {
    "executive_summary": ("summary", "overview", "objective"),
    "challenge": ("challenge", "problem", "pain point", "current state"),
    "solution": ("solution", "approach", "architecture", "deliver"),
    "technology_stack": ("technology", "azure", "aws", "snowflake", "databricks", "python"),
    "business_outcome": ("outcome", "impact", "benefit", "value"),
    "metrics": ("%", "revenue", "cost", "saving", "reduction", "increase"),
    "delivery_team": ("team", "delivery lead", "project manager", "engineer"),
    "lessons_learned": ("lesson", "recommendation", "risk", "caveat"),
}


class OnePagerGenerationError(RuntimeError):
    pass


def indexed_readiness(document_ids: list[str], config: Settings = settings) -> dict:
    requested = {
        value.removeprefix("source_").lstrip("0") or "0"
        for value in document_ids
    }
    selected = [
        document
        for document in load_pilot_documents(config)
        if str(document.doc_id) in requested
    ]
    combined_text = "\n".join(document.raw_text for document in selected).lower()
    coverage = {}
    gaps = []
    for field, terms in COVERAGE_TERMS.items():
        matches = sum(term in combined_text for term in terms)
        status = "available" if matches >= 2 else "partial" if matches == 1 else "missing"
        coverage[field] = status
        if status != "available":
            label = field.replace("_", " ").title()
            gaps.append({
                "field": field,
                "label": label,
                "status": status,
                "message": (
                    f"The selected indexed documents have {status} information "
                    f"for {field.replace('_', ' ')}."
                ),
            })
    return {
        "status": "ready" if not gaps else "ready_with_gaps",
        "selected_document_count": len(selected),
        "coverage": coverage,
        "gaps": gaps,
    }


def _format_evidence(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for chunk in chunks:
        metadata = chunk.document.metadata
        blocks.append(
            f"[SOURCE {chunk.citation_id}]\n"
            f"File: {metadata['file_name']}\n"
            f"Location: {metadata['location_type']} {metadata['location_number']}\n"
            f"{chunk.document.page_content}"
        )
    return "\n\n".join(blocks)


def _section(markdown: str, name: str) -> str:
    match = re.search(
        rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else f"Known gap: {name} was not generated."


def _bullets(value: str) -> list[str]:
    values = [
        re.sub(r"^\s*[-*]\s+", "", line).strip()
        for line in value.splitlines()
        if re.match(r"^\s*[-*]\s+", line)
    ]
    return values or [value.strip()]


def _parse_brief(markdown: str, chunks: list[RetrievedChunk]) -> dict:
    title = re.search(r"^# (.+)$", markdown, flags=re.MULTILINE)
    generated = re.search(
        r"^Generated (.+?)(?:\s+-\s+Sales Brief)?$",
        markdown,
        flags=re.MULTILINE,
    )
    case_study = re.search(
        r"^(.+?\s+-\s+A Blend360 Case Study)\s*$",
        markdown,
        flags=re.MULTILINE,
    )
    sources = {}
    for chunk in chunks:
        metadata = chunk.document.metadata
        document_id = str(metadata["document_id"])
        sources.setdefault(document_id, {
            "document_id": document_id,
            "file_name": str(metadata["file_name"]),
        })
    return {
        "one_pager_id": f"op_{uuid4().hex[:8]}",
        "title": title.group(1).strip() if title else "Project Sales Brief",
        "generated_date": generated.group(1).strip() if generated else date.today().isoformat(),
        "case_study_line": (
            case_study.group(1).strip()
            if case_study
            else "Project - A Blend360 Case Study"
        ),
        "executive_summary": _section(markdown, "Executive Summary"),
        "challenge": _section(markdown, "The Challenge"),
        "solution": _section(markdown, "Our Solution"),
        "key_features": _bullets(_section(markdown, "Key Features")),
        "quantified_outcomes": _bullets(_section(markdown, "Quantified Outcomes")),
        "business_value": _section(markdown, "Business Value"),
        "known_gaps": _bullets(_section(markdown, "Known Gaps / Caveats")),
        "sources_used": list(sources.values()),
        "markdown": markdown.strip(),
    }


def generate_indexed_one_pager(
    document_ids: list[str],
    title: str | None = None,
    config: Settings = settings,
) -> dict:
    if not document_ids:
        raise ValueError("Select at least one indexed document")
    if not os.getenv("OPENAI_API_KEY"):
        raise OnePagerGenerationError("OPENAI_API_KEY is not configured")
    try:
        chunks = retrieve_chunks(
            (
                "client project challenge solution architecture technology features "
                "delivery quantified outcomes metrics business value lessons learned"
            ),
            document_ids=document_ids,
            config=config,
            limit=60,
        )
    except Exception as error:
        log.exception("One-pager evidence retrieval failed")
        raise OnePagerGenerationError("One-pager evidence retrieval failed") from error
    if not chunks:
        raise ValueError("No indexed evidence was found for the selected documents")

    human_input = (
        f"Project name instruction: {title or 'Infer the single project name from the source materials.'}\n"
        f"Generation date: {date.today().isoformat()}\n\n"
        f"Source materials available:\n{_format_evidence(chunks)}"
    )
    try:
        response = ChatOpenAI(
            model=config.chat_model,
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0,
        ).invoke([
            ("system", ONE_PAGER_PROMPT),
            ("human", human_input),
        ])
        markdown = response.content
        if not isinstance(markdown, str) or not markdown.strip():
            raise ValueError("OpenAI returned an empty one-pager")
    except Exception as error:
        log.exception("One-pager generation failed")
        raise OnePagerGenerationError("One-pager generation is currently unavailable") from error

    item = _parse_brief(markdown, chunks)
    data = read_json("one_pagers.json")
    data.append(item)
    write_json("one_pagers.json", data)
    return item

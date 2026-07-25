from io import BytesIO

from langchain_core.documents import Document
from pypdf import PdfReader

from app.core.settings import settings
from app.retrieval.retriever import RetrievedChunk
from app.services.one_pager_service import (
    ONE_PAGER_PROMPT,
    _parse_brief,
    indexed_readiness,
)
from app.services.pdf_service import build_one_pager_pdf


def test_indexed_readiness_resolves_active_chroma_document_ids():
    result = indexed_readiness(["source_000001", "source_000007"], settings)
    assert result["selected_document_count"] == 2
    assert result["status"] in {"ready", "ready_with_gaps"}
    assert any(value != "missing" for value in result["coverage"].values())


def test_runtime_prompt_is_exact_attached_prompt():
    attached = (
        __import__("pathlib").Path.home()
        / "Downloads"
        / "participant_sales_brief_generation_prompt (1).md"
    )
    if attached.exists():
        assert ONE_PAGER_PROMPT == attached.read_text(encoding="utf-8")


def test_parsed_sales_brief_renders_as_one_page_pdf():
    markdown = """# Example Project - Modern Analytics
Generated 2026-07-25 - Sales Brief

Example Project - A Blend360 Case Study

## Executive Summary
Blend360 delivered a grounded analytics solution.

## The Challenge
Reporting was manual.

## Our Solution
The team implemented an automated workflow.

## Key Features
- Automation - Reduces manual work.
- Governance - Improves trust.

## Quantified Outcomes
- Known gap: the provided materials do not include quantified outcomes.

## Business Value
The project demonstrates a reusable analytics capability.

## Known Gaps / Caveats
- Delivery team details are missing.

## Sources Used
- example.pptx, slide 1
"""
    chunk = RetrievedChunk(
        document=Document(
            page_content="Example evidence",
            metadata={
                "document_id": "1",
                "file_name": "example.pptx",
                "location_type": "slide",
                "location_number": 1,
            },
        ),
        relevance_score=0.8,
        citation_id="1:slide:1:1",
    )
    item = _parse_brief(markdown, [chunk])
    pdf = build_one_pager_pdf(item)
    assert pdf.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(pdf)).pages) == 1

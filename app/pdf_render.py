"""Render an OnePager dict to a PDF (bytes) with reportlab, in the style of the
supplied `sample_chewy_sales_brief.pdf`: centered title, "Generated {date} - Sales
Brief", case-study line, blue section headings, bulleted lists, and a footer.

Pure-Python (reportlab) — no system libraries, safe on Windows.
"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
)

_BLUE = HexColor("#1F4E79")
_SLATE = HexColor("#475569")
_FOOTER = "Source-grounded PIH Hackathon artifact"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("BriefTitle", parent=base["Title"], fontSize=22,
                                 textColor=_BLUE, alignment=TA_CENTER, spaceAfter=6),
        "sub": ParagraphStyle("BriefSub", parent=base["Normal"], fontSize=10,
                              textColor=_SLATE, alignment=TA_CENTER, spaceAfter=2),
        "h2": ParagraphStyle("BriefH2", parent=base["Heading2"], fontSize=13,
                             textColor=_BLUE, spaceBefore=14, spaceAfter=4),
        "body": ParagraphStyle("BriefBody", parent=base["Normal"], fontSize=10,
                               leading=14, spaceAfter=4),
        "bullet": ParagraphStyle("BriefBullet", parent=base["Normal"], fontSize=10,
                                 leading=14),
    }


def _esc(text: str) -> str:
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_SLATE)
    canvas.drawCentredString(LETTER[0] / 2, 0.5 * inch, _FOOTER)
    canvas.restoreState()


def render_pdf(one_pager: dict) -> bytes:
    s = _styles()
    story = []

    story.append(Paragraph(_esc(one_pager.get("title", "Sales Brief")), s["title"]))
    story.append(Paragraph(f"Generated {_esc(one_pager.get('generated_date', ''))} - Sales Brief", s["sub"]))
    story.append(Paragraph(_esc(one_pager.get("case_study_line", "")), s["sub"]))
    story.append(Spacer(1, 10))

    def section(title: str, body: str):
        if body:
            story.append(Paragraph(title, s["h2"]))
            for para in str(body).split("\n"):
                if para.strip():
                    story.append(Paragraph(_esc(para), s["body"]))

    def bullets(title: str, items: list[str]):
        items = [i for i in (items or []) if str(i).strip()]
        if items:
            story.append(Paragraph(title, s["h2"]))
            story.append(ListFlowable(
                [ListItem(Paragraph(_esc(i), s["bullet"]), leftIndent=12) for i in items],
                bulletType="bullet", start="•", leftIndent=14))

    section("Executive Summary", one_pager.get("executive_summary"))
    section("The Challenge", one_pager.get("challenge"))
    section("Our Solution", one_pager.get("solution"))
    bullets("Key Features", one_pager.get("key_features"))
    bullets("Quantified Outcomes", one_pager.get("quantified_outcomes"))
    section("Business Value", one_pager.get("business_value"))
    bullets("Known Gaps / Caveats", one_pager.get("known_gaps"))

    # Sources Used: prefer the richer slide-level lines the LLM produced; else the file list.
    source_lines = one_pager.get("_source_lines") or [
        f"{src.get('file_name')} ({src.get('document_id')})"
        for src in one_pager.get("sources_used", [])
    ]
    bullets("Sources Used", source_lines)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER, topMargin=0.7 * inch, bottomMargin=0.8 * inch,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
        title=one_pager.get("title", "Sales Brief"))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


def build_one_pager_pdf(one_pager: dict) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=one_pager["title"],
        author="Project Intelligence Hub",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="PIHTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=29,
        textColor=colors.HexColor("#172554"),
        alignment=TA_CENTER,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="PIHSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1D4ED8"),
        spaceBefore=10,
        spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="PIHBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="PIHMeta",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748B"),
        alignment=TA_CENTER,
    ))

    story = [
        Paragraph("PROJECT INTELLIGENCE HUB", styles["PIHMeta"]),
        Spacer(1, 4),
        Paragraph(escape(one_pager["title"]), styles["PIHTitle"]),
        Paragraph(escape(one_pager["case_study_line"]), styles["PIHMeta"]),
        Paragraph(f"Generated {escape(one_pager['generated_date'])}", styles["PIHMeta"]),
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#BFDBFE")),
    ]

    def section(title: str, text: str) -> None:
        story.extend([
            Paragraph(title, styles["PIHSection"]),
            Paragraph(escape(text), styles["PIHBody"]),
        ])

    def bullet_section(title: str, values: list[str]) -> None:
        story.append(Paragraph(title, styles["PIHSection"]))
        if values:
            story.append(ListFlowable(
                [ListItem(Paragraph(escape(value), styles["PIHBody"])) for value in values],
                bulletType="bullet",
                leftIndent=14,
                bulletColor=colors.HexColor("#2563EB"),
            ))
        else:
            story.append(Paragraph("No items reported.", styles["PIHBody"]))

    section("Executive Summary", one_pager["executive_summary"])
    section("The Challenge", one_pager["challenge"])
    section("Our Solution", one_pager["solution"])
    bullet_section("Key Features", one_pager["key_features"])
    bullet_section("Quantified Outcomes", one_pager["quantified_outcomes"])
    section("Business Value", one_pager["business_value"])
    bullet_section("Known Gaps / Caveats", one_pager["known_gaps"])
    story.append(PageBreak())
    story.append(Paragraph("Sources Used", styles["PIHSection"]))
    story.append(ListFlowable(
        [
            ListItem(Paragraph(
                f"{escape(source['file_name'])} ({escape(source['document_id'])})",
                styles["PIHBody"],
            ))
            for source in one_pager["sources_used"]
        ],
        bulletType="bullet",
        leftIndent=14,
    ))

    document.build(story)
    return buffer.getvalue()

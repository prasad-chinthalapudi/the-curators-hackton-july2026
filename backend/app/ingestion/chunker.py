import re
from collections.abc import Iterable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ingestion.models import ExtractedDocument

BOUNDARIES = {
    ".pptx": ("slide", re.compile(r"\n?--- SLIDE (\d+) ---\n?", re.IGNORECASE)),
    ".pdf": ("page", re.compile(r"\n?--- PAGE (\d+) ---\n?", re.IGNORECASE)),
}
TECHNOLOGIES = (
    "Azure", "AWS", "Snowflake", "Databricks", "ADF", "Redshift", "Power BI",
    "Python", "PySpark", "XGBoost", "Machine Learning", "GenAI", "LangChain",
)
INDUSTRIES = (
    "Healthcare", "Life Sciences", "Manufacturing", "Retail", "Travel",
    "Insurance", "Banking", "Hospitality", "Financial Services",
)


def _classify(document: ExtractedDocument) -> tuple[list[str], str]:
    searchable = f"{document.filename}\n{document.raw_text}".lower()
    technologies = [value for value in TECHNOLOGIES if value.lower() in searchable]
    industry = next((value for value in INDUSTRIES if value.lower() in searchable), "Unclassified")
    return technologies, industry


def _base_metadata(document: ExtractedDocument, dataset: str) -> dict:
    technologies, industry = _classify(document)
    year_match = re.search(r"(?<!\d)(20\d{2})(?:\d{4})?(?!\d)", document.filename)
    return {
        "document_id": f"source_{document.doc_id:06}",
        "source_doc_id": document.doc_id,
        "file_name": document.filename,
        "file_type": document.file_type.lstrip(".").lower(),
        "relative_path": document.relative_path,
        "industry": industry,
        "technologies": "|".join(technologies) if technologies else "Unclassified",
        "year": int(year_match.group(1)) if year_match else 0,
        "dataset": dataset,
    }


def _bounded_parts(text: str, pattern: re.Pattern[str]) -> Iterable[tuple[int, str]]:
    matches = list(pattern.finditer(text))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            yield int(match.group(1)), content


def _clean_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\x0b", " ").replace("\ufffd", "-")).strip()


def chunk_document(document: ExtractedDocument, dataset: str) -> list[Document]:
    base = _base_metadata(document, dataset)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)
    boundary = BOUNDARIES.get(document.file_type.lower())
    chunks: list[Document] = []
    if boundary:
        location_type, pattern = boundary
        sections = list(_bounded_parts(document.raw_text, pattern))
        if sections:
            for location_number, content in sections:
                for sub_index, text in enumerate(splitter.split_text(content), 1):
                    chunks.append(Document(page_content=_clean_text(text), metadata={
                        **base, "location_type": location_type,
                        "location_number": location_number, "sub_chunk": sub_index,
                    }))
            return chunks

    location_type = "sheet_chunk" if document.file_type.lower() == ".xlsx" else "document_chunk"
    for index, text in enumerate(splitter.split_text(document.raw_text), 1):
        chunks.append(Document(page_content=_clean_text(text), metadata={
            **base, "location_type": location_type, "location_number": index, "sub_chunk": 1,
        }))
    return chunks

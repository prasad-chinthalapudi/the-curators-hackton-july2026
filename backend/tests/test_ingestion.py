import json

import pytest

from app.core.settings import settings
from app.ingestion.chunker import chunk_document
from app.ingestion.chroma_indexer import create_vector_store
from app.ingestion.index_loader import build_pilot_chunks, load_pilot_documents


def test_pilot_manifest_has_14_documents_covering_all_types():
    documents = load_pilot_documents(settings)
    assert len(documents) == 14
    counts = {
        file_type: sum(document.file_type == file_type for document in documents)
        for file_type in {document.file_type for document in documents}
    }
    assert counts == {".pptx": 4, ".docx": 4, ".pdf": 4, ".xlsx": 2}


def test_manifest_is_unique_and_matches_source_types():
    manifest = json.loads(settings.pilot_manifest.read_text(encoding="utf-8"))
    entries = manifest["documents"]
    assert len({entry["doc_id"] for entry in entries}) == len(entries)
    documents = {document.doc_id: document for document in load_pilot_documents(settings)}
    assert all(documents[entry["doc_id"]].file_type == entry["file_type"] for entry in entries)


def test_chunking_preserves_powerpoint_slide_citations():
    document = next(item for item in load_pilot_documents(settings) if item.file_type == ".pptx")
    chunks = chunk_document(document, settings.dataset)
    assert chunks
    assert all(chunk.metadata["location_type"] == "slide" for chunk in chunks)
    assert all(chunk.metadata["location_number"] >= 1 for chunk in chunks)


def test_build_pilot_chunks_has_metadata_for_every_file_type():
    chunks = build_pilot_chunks(settings)
    assert {chunk.metadata["file_type"] for chunk in chunks} == {"pptx", "docx", "pdf", "xlsx"}
    assert all(chunk.metadata["dataset"] == settings.dataset for chunk in chunks)
    assert all(chunk.page_content.strip() for chunk in chunks)


def test_vector_store_requires_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        create_vector_store(settings)

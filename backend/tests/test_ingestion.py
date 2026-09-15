import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.settings import settings
from app.ingestion.chunker import chunk_document
from app.ingestion.chroma_indexer import clear_vector_store_cache, create_vector_store
from app.ingestion.index_loader import build_pilot_chunks, load_pilot_documents


def test_pilot_manifest_loads_every_selected_document():
    manifest = json.loads(settings.pilot_manifest.read_text(encoding="utf-8"))
    documents = load_pilot_documents(settings)
    assert len(documents) == len(manifest["documents"]) == 16
    counts = {
        file_type: sum(document.file_type == file_type for document in documents)
        for file_type in {document.file_type for document in documents}
    }
    assert counts == {".pptx": 11, ".docx": 3, ".xlsx": 2}


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


def test_filename_date_populates_year_metadata():
    document = next(item for item in load_pilot_documents(settings) if item.filename.startswith("2026"))
    chunks = chunk_document(document, settings.dataset)
    assert chunks[0].metadata["year"] == 2026


def test_build_pilot_chunks_has_metadata_for_every_file_type():
    chunks = build_pilot_chunks(settings)
    expected_types = {
        item.file_type.removeprefix(".")
        for item in load_pilot_documents(settings)
    }
    assert {chunk.metadata["file_type"] for chunk in chunks} == expected_types
    assert all(chunk.metadata["dataset"] == settings.dataset for chunk in chunks)
    assert all(chunk.page_content.strip() for chunk in chunks)
    assert all("\x0b" not in chunk.page_content for chunk in chunks)
    assert all("\ufffd" not in chunk.page_content for chunk in chunks)


def test_vector_store_requires_openai_key(monkeypatch):
    clear_vector_store_cache()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        create_vector_store(settings)


def test_vector_store_factory_is_process_cached(monkeypatch, tmp_path):
    import app.ingestion.chroma_indexer as indexer

    calls = 0

    class FakeChroma:
        def __init__(self, **kwargs):
            nonlocal calls
            calls += 1

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(indexer, "Chroma", FakeChroma)
    monkeypatch.setattr(indexer, "OpenAIEmbeddings", lambda **kwargs: object())
    clear_vector_store_cache()
    first = create_vector_store(settings)
    second = create_vector_store(settings)
    assert first is second
    assert calls == 1
    clear_vector_store_cache()


def test_vector_store_factory_serializes_concurrent_initialization(monkeypatch):
    import app.ingestion.chroma_indexer as indexer

    calls = 0

    class SlowFakeChroma:
        def __init__(self, **kwargs):
            nonlocal calls
            calls += 1
            time.sleep(0.05)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(indexer, "Chroma", SlowFakeChroma)
    monkeypatch.setattr(indexer, "OpenAIEmbeddings", lambda **kwargs: object())
    clear_vector_store_cache()
    with ThreadPoolExecutor(max_workers=8) as executor:
        stores = list(executor.map(lambda _: create_vector_store(settings), range(16)))
    assert len({id(store) for store in stores}) == 1
    assert calls == 1
    clear_vector_store_cache()

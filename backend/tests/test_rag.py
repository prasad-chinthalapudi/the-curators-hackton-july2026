from langchain_core.documents import Document
from chromadb.errors import NotFoundError

from app.core.settings import settings
from app.retrieval.retriever import RetrievedChunk, build_chroma_filter
from app.schemas.models import ChatRequest, SearchFilters, StructuredAnswer
from app.services import rag_service


def _chunk(citation_id: str, file_name: str = "project.pptx") -> RetrievedChunk:
    document_id, location_type, location_number, sub_chunk = citation_id.split(":")
    return RetrievedChunk(
        document=Document(
            page_content="The project reduced reporting time by 35 percent.",
            metadata={
                "document_id": document_id,
                "file_name": file_name,
                "file_type": "pptx",
                "location_type": location_type,
                "location_number": int(location_number),
                "sub_chunk": int(sub_chunk),
            },
        ),
        relevance_score=0.82,
        citation_id=citation_id,
    )


def test_chroma_filter_supports_selected_documents_and_metadata():
    expression = build_chroma_filter(
        SearchFilters(
            file_types=["pptx"],
            industries=["Healthcare"],
            year_from=2024,
            year_to=2026,
        ),
        ["source_000004", "source_000845"],
        settings,
    )
    assert expression["$and"] == [
        {"dataset": settings.dataset},
        {"document_id": {"$in": ["source_000004", "source_000845"]}},
        {"file_type": {"$in": ["pptx"]}},
        {"industry": {"$in": ["Healthcare"]}},
        {"year": {"$gte": 2024}},
        {"year": {"$lte": 2026}},
    ]


def test_search_and_chat_can_request_different_retrieval_depth(monkeypatch):
    captured = {}

    class FakeStore:
        def similarity_search_with_score(self, query, k, filter):
            captured["k"] = k
            return []

    monkeypatch.setattr("app.retrieval.retriever.create_vector_store", lambda config: FakeStore())
    from app.retrieval.retriever import retrieve_chunks
    retrieve_chunks("query", config=settings, limit=40)
    assert captured["k"] == 160


def test_retrieval_reconnects_after_collection_is_replaced(monkeypatch):
    calls = {"stale": 0, "fresh": 0, "refresh": 0}

    class StaleStore:
        def similarity_search_with_score(self, query, k, filter):
            calls["stale"] += 1
            raise NotFoundError("Collection does not exist")

    class FreshStore:
        def similarity_search_with_score(self, query, k, filter):
            calls["fresh"] += 1
            return []

    monkeypatch.setattr(
        "app.retrieval.retriever.create_vector_store",
        lambda config: StaleStore(),
    )

    def refresh(config):
        calls["refresh"] += 1
        return FreshStore()

    monkeypatch.setattr("app.retrieval.retriever.refresh_vector_store", refresh)
    from app.retrieval.retriever import retrieve_chunks

    assert retrieve_chunks("query", config=settings) == []
    assert calls == {"stale": 1, "fresh": 1, "refresh": 1}


def test_empty_retrieval_skips_generation(monkeypatch):
    monkeypatch.setattr(rag_service, "retrieve_chunks", lambda *args, **kwargs: [])
    response = rag_service.answer_query(ChatRequest(message="Unknown question"))
    assert response.citations == []
    assert response.retrieved_chunk_count == 0
    assert response.missing_information


def test_structured_answer_returns_only_model_used_citations(monkeypatch):
    chunks = [
        _chunk("source_000004:slide:10:1"),
        _chunk("source_000845:slide:2:1", "healthcare.pptx"),
    ]
    monkeypatch.setattr(rag_service, "retrieve_chunks", lambda *args, **kwargs: chunks)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class FakeStructuredModel:
        def invoke(self, messages):
            assert "CITATION source_000004:slide:10:1" in messages[1][1]
            return StructuredAnswer(
                answer="Reporting time improved by 35%.",
                used_citation_ids=["source_000004:slide:10:1", "invented:page:1:1"],
            )

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            assert kwargs["model"] == settings.chat_model

        def with_structured_output(self, schema, method):
            assert schema is StructuredAnswer
            assert method == "json_schema"
            return FakeStructuredModel()

    monkeypatch.setattr(rag_service, "ChatOpenAI", FakeChatOpenAI)
    response = rag_service.answer_query(ChatRequest(message="What improved?"))
    assert response.answer == "Reporting time improved by 35%."
    assert len(response.citations) == 1
    assert response.citations[0].citation_id == "source_000004:slide:10:1"


def test_chat_endpoint_maps_retrieval_failure_to_503(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    def fail(_request):
        raise rag_service.RetrievalUnavailableError("Document retrieval is currently unavailable")

    monkeypatch.setattr(rag_service, "answer_query", fail)
    response = TestClient(app).post("/api/chat", json={"message": "Hello"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Document retrieval is currently unavailable"

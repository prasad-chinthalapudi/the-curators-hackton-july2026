from dataclasses import dataclass

from chromadb.errors import NotFoundError
from langchain_core.documents import Document

from app.core.settings import Settings, settings
from app.ingestion.chroma_indexer import create_vector_store, refresh_vector_store
from app.schemas.models import SearchFilters


@dataclass(frozen=True)
class RetrievedChunk:
    document: Document
    relevance_score: float
    citation_id: str


def build_chroma_filter(
    filters: SearchFilters,
    document_ids: list[str],
    config: Settings = settings,
) -> dict:
    clauses: list[dict] = [{"dataset": config.dataset}]
    if document_ids:
        clauses.append({"document_id": {"$in": document_ids}})
    if filters.file_types:
        clauses.append({"file_type": {"$in": filters.file_types}})
    if filters.industries:
        clauses.append({"industry": {"$in": filters.industries}})
    if filters.year_from is not None:
        clauses.append({"year": {"$gte": filters.year_from}})
    if filters.year_to is not None:
        clauses.append({"year": {"$lte": filters.year_to}})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _matches_technology(metadata: dict, selected: list[str]) -> bool:
    available = set(str(metadata.get("technologies", "")).split("|"))
    return not selected or bool(available.intersection(selected))


def _citation_id(document: Document) -> str:
    metadata = document.metadata
    return (
        f"{metadata['document_id']}:{metadata['location_type']}:"
        f"{metadata['location_number']}:{metadata.get('sub_chunk', 1)}"
    )


def retrieve_chunks(
    query: str,
    filters: SearchFilters | None = None,
    document_ids: list[str] | None = None,
    config: Settings = settings,
    limit: int | None = None,
) -> list[RetrievedChunk]:
    active_filters = filters or SearchFilters()
    store = create_vector_store(config)
    result_limit = limit or config.retrieval_top_k
    candidate_count = max(result_limit * 4, 24)
    chroma_filter = build_chroma_filter(active_filters, document_ids or [], config)
    try:
        candidates = store.similarity_search_with_score(
            query,
            k=candidate_count,
            filter=chroma_filter,
        )
    except NotFoundError:
        # A reset creates a new internal collection ID. Reconnect once when a
        # long-running API process still holds the deleted collection object.
        store = refresh_vector_store(config)
        candidates = store.similarity_search_with_score(
            query,
            k=candidate_count,
            filter=chroma_filter,
        )
    results: list[RetrievedChunk] = []
    seen: set[str] = set()
    for document, distance in candidates:
        score = 1.0 / (1.0 + max(0.0, float(distance)))
        citation_id = _citation_id(document)
        if citation_id in seen:
            continue
        if score < config.min_relevance_score:
            continue
        if not _matches_technology(document.metadata, active_filters.technologies):
            continue
        seen.add(citation_id)
        results.append(RetrievedChunk(document, score, citation_id))
        if len(results) >= result_limit:
            break
    return results

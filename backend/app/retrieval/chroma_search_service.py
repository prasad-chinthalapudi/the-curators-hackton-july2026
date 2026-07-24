from collections import defaultdict
from datetime import date
from math import ceil

from app.core.settings import Settings, settings
from app.ingestion.chunker import _base_metadata
from app.ingestion.index_loader import load_pilot_documents
from app.ingestion.chroma_indexer import create_vector_store
from app.schemas.models import SearchRequest


def _filter_expression(request: SearchRequest, config: Settings) -> dict | None:
    clauses: list[dict] = [{"dataset": config.dataset}]
    filters = request.filters
    if filters.file_types:
        clauses.append({"file_type": {"$in": filters.file_types}})
    if filters.industries:
        clauses.append({"industry": {"$in": filters.industries}})
    if filters.year_from is not None:
        clauses.append({"year": {"$gte": filters.year_from}})
    if filters.year_to is not None:
        clauses.append({"year": {"$lte": filters.year_to}})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _technology_match(technology_string: str, selected: list[str]) -> bool:
    values = set(technology_string.split("|"))
    return not selected or bool(values.intersection(selected))


def _coverage() -> dict[str, str]:
    return {
        "executive_summary": "available", "challenge": "available",
        "solution": "available", "technology_stack": "available",
        "business_outcome": "partial", "metrics": "partial",
        "delivery_team": "missing", "lessons_learned": "partial",
    }


def search_chroma(request: SearchRequest, config: Settings = settings) -> dict:
    store = create_vector_store(config)
    candidates = store.similarity_search_with_relevance_scores(
        request.query or "project case study",
        k=max(30, request.page_size * 4),
        filter=_filter_expression(request, config),
    )
    grouped: dict[str, list[tuple]] = defaultdict(list)
    for chunk, score in candidates:
        if _technology_match(str(chunk.metadata.get("technologies", "")), request.filters.technologies):
            grouped[str(chunk.metadata["document_id"])].append((chunk, max(0.0, min(1.0, score))))

    documents = []
    for document_id, matches in grouped.items():
        matches.sort(key=lambda item: item[1], reverse=True)
        best_chunk, best_score = matches[0]
        metadata = best_chunk.metadata
        documents.append({
            "document_id": document_id,
            "file_name": metadata["file_name"],
            "file_type": metadata["file_type"],
            "match_score": round(best_score, 4),
            "summary": best_chunk.page_content[:360].strip(),
            "tags": [metadata["industry"], *str(metadata["technologies"]).split("|")[:2]],
            "technologies": str(metadata["technologies"]).split("|"),
            "industry": metadata["industry"],
            "year": int(metadata.get("year") or date.today().year),
            "added_on": date.today().isoformat(),
            "source_locations": [
                {
                    "location_type": chunk.metadata["location_type"],
                    "location_number": int(chunk.metadata["location_number"]),
                    "excerpt": chunk.page_content[:260].strip(),
                }
                for chunk, _ in matches[:3]
            ],
            "coverage": _coverage(),
        })
    documents.sort(key=lambda item: item["match_score"], reverse=True)
    total = len(documents)
    start = (request.page - 1) * request.page_size
    page_documents = documents[start:start + request.page_size]
    technologies = sorted({technology for item in documents for technology in item["technologies"]})
    industries = sorted({item["industry"] for item in documents})
    pilot_metadata = [_base_metadata(document, config.dataset) for document in load_pilot_documents(config)]
    return {
        "query": request.query,
        "total_documents": total,
        "page": request.page,
        "page_size": request.page_size,
        "total_pages": max(1, ceil(total / request.page_size)),
        "understanding": {
            "summary": "Results are retrieved semantically from the PIH Chroma pilot collection.",
            "documents_found": total,
            "related_clusters": min(3, len(industries)),
            "key_technologies_count": len(technologies),
            "common_technologies": technologies[:5],
            "likely_industries": industries,
            "confidence": round(max((item["match_score"] for item in documents), default=0.0), 2),
        },
        "documents": page_documents,
        "facets": {
            "file_types": sorted({str(item["file_type"]).lstrip(".") for item in pilot_metadata}),
            "technologies": sorted({
                technology
                for item in pilot_metadata
                for technology in str(item["technologies"]).split("|")
            }),
            "industries": sorted({str(item["industry"]) for item in pilot_metadata}),
            "years": sorted({int(item["year"]) for item in pilot_metadata if int(item["year"]) > 0}, reverse=True),
        },
    }

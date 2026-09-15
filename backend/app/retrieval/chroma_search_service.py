from collections import defaultdict
from datetime import date
from math import ceil

from app.core.settings import Settings, settings
from app.ingestion.chunker import _base_metadata
from app.ingestion.index_loader import load_pilot_documents
from app.retrieval.retriever import retrieve_chunks
from app.schemas.models import SearchRequest

MINIMUM_MATCH_SCORE = 0.50
MAXIMUM_VISIBLE_DOCUMENTS = 10


def _coverage() -> dict[str, str]:
    return {
        "executive_summary": "available", "challenge": "available",
        "solution": "available", "technology_stack": "available",
        "business_outcome": "partial", "metrics": "partial",
        "delivery_team": "missing", "lessons_learned": "partial",
    }


def search_chroma(request: SearchRequest, config: Settings = settings) -> dict:
    candidates = retrieve_chunks(
        request.query or "project case study",
        request.filters,
        config=config,
        limit=max(40, request.page_size * 5),
    )
    grouped: dict[str, list[tuple]] = defaultdict(list)
    for candidate in candidates:
        chunk = candidate.document
        grouped[str(chunk.metadata["document_id"])].append((chunk, candidate.relevance_score))

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
    hidden_low_confidence_count = sum(
        item["match_score"] < MINIMUM_MATCH_SCORE for item in documents
    )
    if not request.include_low_confidence:
        documents = [
            item for item in documents
            if item["match_score"] >= MINIMUM_MATCH_SCORE
        ]
    documents = documents[:MAXIMUM_VISIBLE_DOCUMENTS]
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
        "hidden_low_confidence_count": (
            0 if request.include_low_confidence else hidden_low_confidence_count
        ),
        "minimum_match_score": MINIMUM_MATCH_SCORE,
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

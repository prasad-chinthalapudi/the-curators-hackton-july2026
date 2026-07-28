"""/api adapter router — reshapes the RAG backend into the frontend's
document-search + one-pager contract (see app/api_schemas.py, which mirrors
frontend/src/types/index.ts). Mounted from app/main.py.

Existing /query, /facets, /health (RAG contract) are untouched.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import Counter
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from . import config, onepager
from . import retrieve_docling as rd
from .api_schemas import (
    Coverage, Document, Facets, GenerateRequest, IdsRequest, KnowledgeRequest,
    OnePager, Readiness, SearchRequest, SearchResponse, Understanding,
)

log = logging.getLogger("pih.api")
router = APIRouter(prefix="/api")

SEARCH_CANDIDATES = 120     # chunk hits to pull before aggregating into documents
_METRIC_RE = re.compile(r"\d+\s?%|\$\s?\d|\b\d+(?:\.\d+)?\s?(?:million|billion|mm|m|k|x)\b", re.I)


# --------------------------------------------------------------------------- #
# Search adapter: chunk hits -> ranked documents + understanding + facets.
# --------------------------------------------------------------------------- #
def _rescale(raw: float, lo: float, hi: float) -> float:
    """Map a cosine score into a readable 0.55-0.99 band for the UI bar."""
    if hi <= lo:
        return 0.85
    return round(0.55 + 0.44 * (raw - lo) / (hi - lo), 3)


def _heuristic_coverage(recs: list[dict]) -> Coverage:
    text = " ".join(r.get("text", "") for r in recs)
    meta = recs[0]
    has_metric = bool(_METRIC_RE.search(text))
    return Coverage(
        executive_summary="available" if recs else "missing",
        challenge="partial",
        solution="available" if recs else "missing",
        technology_stack="available" if meta.get("technologies") else "partial",
        business_outcome="available" if has_metric else "partial",
        metrics="available" if has_metric else "missing",
        delivery_team="available" if meta.get("poc_name") else "missing",
        lessons_learned="missing",
    )


def _aggregate(hits: list[dict]) -> list[dict]:
    """Group chunk hits by doc_id, keeping the best score + best-scoring chunk."""
    best: dict[str, dict] = {}
    for h in hits:
        doc_id = h["doc_id"]
        if doc_id not in best or h["score"] > best[doc_id]["score"]:
            best[doc_id] = h
    docs = list(best.values())
    docs.sort(key=lambda h: h["score"], reverse=True)
    return docs


def _to_document(hit: dict, lo: float, hi: float) -> Document:
    doc_id = hit["doc_id"]
    recs = rd.get_document(doc_id)
    techs = hit.get("technologies") or []
    inds = hit.get("industries") or []
    modified = hit.get("modified") or ""
    added_on = modified[:10] if isinstance(modified, str) else ""
    snippet = (hit.get("text") or "").strip().replace("\n", " ")
    if len(snippet) > 240:
        snippet = snippet[:240].rsplit(" ", 1)[0] + "…"
    return Document(
        document_id=doc_id,
        file_name=hit.get("filename") or doc_id,
        file_type=hit.get("doc_type") or "",
        match_score=_rescale(hit["score"], lo, hi),
        summary=snippet,
        tags=list(dict.fromkeys([*techs, *inds])),
        technologies=techs,
        industry=inds[0] if inds else "",
        year=hit.get("year"),
        added_on=added_on,
        coverage=_heuristic_coverage(recs or [hit]),
    )


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    # Translate the frontend filter shape (file_types) into retrieve_docling's (doc_types).
    f = req.filters
    filters = {
        "doc_types": f.file_types, "technologies": f.technologies,
        "industries": f.industries, "year_from": f.year_from, "year_to": f.year_to,
    }
    has_filter = any([f.file_types, f.technologies, f.industries,
                      f.year_from is not None, f.year_to is not None])
    try:
        hits = rd.search(req.query, k=SEARCH_CANDIDATES, filters=filters if has_filter else None)
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"error": "no_artifact",
                            "detail": "run embed_docling + enrich_metadata first"})
    except Exception as e:
        log.error("/api/search failed: %s", e)
        return JSONResponse(status_code=500, content={"error": "search_failed", "detail": str(e)})

    agg = _aggregate(hits)
    scores = [h["score"] for h in agg]
    lo, hi = (min(scores), max(scores)) if scores else (0.0, 1.0)

    page = max(1, req.page)
    page_size = max(1, req.page_size)
    total = len(agg)
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    page_hits = agg[start:start + page_size]
    documents = [_to_document(h, lo, hi) for h in page_hits]

    # Understanding block: grounded summary + aggregated signals across ALL matched docs.
    tech_counter = Counter(t for h in agg for t in (h.get("technologies") or []))
    ind_counter = Counter(i for h in agg for i in (h.get("industries") or []))
    try:
        summary = rd.answer_query(req.query, k=config.TOP_K,
                                  filters=filters if has_filter else None)["answer"]
    except Exception as e:
        log.warning("understanding summary failed: %s", e)
        summary = ""
    confidence = round(min(0.99, max(0.4, hi * 1.6)), 2) if scores else 0.0
    understanding = Understanding(
        summary=summary,
        documents_found=total,
        related_clusters=len(ind_counter),
        key_technologies_count=len(tech_counter),
        common_technologies=[t for t, _ in tech_counter.most_common(6)],
        likely_industries=[i for i, _ in ind_counter.most_common(4)],
        confidence=confidence,
    )

    try:
        fc = rd.facets()
        facets = Facets(
            file_types=list(fc.get("doc_types", {}).keys()),
            technologies=list(fc.get("technologies", {}).keys()),
            industries=list(fc.get("industries", {}).keys()),
            years=sorted(int(y) for y in fc.get("years", {}).keys()),
        )
    except Exception:
        facets = Facets()

    return SearchResponse(
        query=req.query, total_documents=total, page=page, page_size=page_size,
        total_pages=total_pages, understanding=understanding,
        documents=documents, facets=facets,
    )


# --------------------------------------------------------------------------- #
# One-pager (sales brief) endpoints.
# --------------------------------------------------------------------------- #
@router.post("/one-pagers/readiness", response_model=Readiness)
def readiness(req: IdsRequest):
    try:
        return Readiness(**onepager.assess_readiness(req.document_ids))
    except Exception as e:
        log.error("/api/one-pagers/readiness failed: %s", e)
        return JSONResponse(status_code=500, content={"error": "readiness_failed", "detail": str(e)})


@router.post("/one-pagers", response_model=OnePager)
def create_one_pager(req: GenerateRequest):
    try:
        result = onepager.generate_one_pager(req.document_ids, req.title)
        result.pop("_source_lines", None)   # PDF-only extra, not in the OnePager contract
        return OnePager(**result)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": "bad_request", "detail": str(e)})
    except Exception as e:
        log.error("/api/one-pagers failed: %s", e)
        return JSONResponse(status_code=500, content={"error": "generation_failed", "detail": str(e)})


@router.get("/one-pagers/{one_pager_id}", response_model=OnePager)
def get_one_pager(one_pager_id: str):
    data = onepager.load_one_pager(one_pager_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    data.pop("_source_lines", None)
    return OnePager(**data)


@router.get("/one-pagers/{one_pager_id}/pdf")
def get_one_pager_pdf(one_pager_id: str):
    path = onepager.one_pager_pdf_path(one_pager_id)
    if not path:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return FileResponse(path, media_type="application/pdf",
                        filename=f"{one_pager_id}-one-pager.pdf")


# --------------------------------------------------------------------------- #
# Knowledge capture.
# --------------------------------------------------------------------------- #
@router.post("/knowledge")
def save_knowledge(req: KnowledgeRequest):
    try:
        os.makedirs(os.path.dirname(config.KNOWLEDGE_FILE) or ".", exist_ok=True)
        entry = {"timestamp": datetime.now().isoformat(), **req.model_dump()}
        with open(config.KNOWLEDGE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"ok": True, "saved": entry}
    except Exception as e:
        log.error("/api/knowledge failed: %s", e)
        return JSONResponse(status_code=500, content={"error": "knowledge_failed", "detail": str(e)})

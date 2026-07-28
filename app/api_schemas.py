"""Pydantic models for the /api adapter — a byte-for-byte mirror of the frontend
TypeScript contract in `frontend/src/types/index.ts`.

These intentionally differ from app/schemas.py (the RAG contract). The frontend is
a document-search + one-pager workspace, so the field names here match the TS
interfaces exactly (e.g. `file_types` not `doc_types`, `match_score` 0-1).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["available", "partial", "missing"]

# The 8 fixed coverage sections (order + keys mirror the TS `Coverage` interface).
COVERAGE_FIELDS = [
    "executive_summary", "challenge", "solution", "technology_stack",
    "business_outcome", "metrics", "delivery_team", "lessons_learned",
]


class Coverage(BaseModel):
    executive_summary: Status = "missing"
    challenge: Status = "missing"
    solution: Status = "missing"
    technology_stack: Status = "missing"
    business_outcome: Status = "missing"
    metrics: Status = "missing"
    delivery_team: Status = "missing"
    lessons_learned: Status = "missing"


# ---- search ---------------------------------------------------------------- #
class Filters(BaseModel):
    file_types: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None


class SearchRequest(BaseModel):
    query: str
    filters: Filters = Field(default_factory=Filters)
    page: int = 1
    page_size: int = 10
    sort_by: str = "relevance"


class Document(BaseModel):
    document_id: str
    file_name: str
    file_type: str
    match_score: float           # 0-1 (UI multiplies by 100)
    summary: str
    tags: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    industry: str = ""
    year: int | None = None
    added_on: str = ""
    coverage: Coverage = Field(default_factory=Coverage)


class Understanding(BaseModel):
    summary: str = ""
    documents_found: int = 0
    related_clusters: int = 0
    key_technologies_count: int = 0
    common_technologies: list[str] = Field(default_factory=list)
    likely_industries: list[str] = Field(default_factory=list)
    confidence: float = 0.0      # 0-1


class Facets(BaseModel):
    file_types: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    total_documents: int
    page: int
    page_size: int
    total_pages: int
    understanding: Understanding
    documents: list[Document]
    facets: Facets


# ---- one-pagers ------------------------------------------------------------ #
class Gap(BaseModel):
    field: str
    label: str
    status: Status
    message: str


class Readiness(BaseModel):
    status: str                  # e.g. "ready" | "partial" | "needs_input"
    selected_document_count: int
    coverage: Coverage
    gaps: list[Gap] = Field(default_factory=list)


class SourceRef(BaseModel):
    document_id: str
    file_name: str


class OnePager(BaseModel):
    one_pager_id: str
    title: str
    generated_date: str
    case_study_line: str
    executive_summary: str
    challenge: str
    solution: str
    key_features: list[str] = Field(default_factory=list)
    quantified_outcomes: list[str] = Field(default_factory=list)
    business_value: str
    known_gaps: list[str] = Field(default_factory=list)
    sources_used: list[SourceRef] = Field(default_factory=list)


# ---- request bodies for the one-pager + knowledge endpoints ---------------- #
class IdsRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    title: str | None = None


class KnowledgeRequest(BaseModel):
    question: str
    answer: str
    related_document_ids: list[str] = Field(default_factory=list)
    contributor: str = ""

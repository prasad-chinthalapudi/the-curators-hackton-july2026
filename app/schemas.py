"""Pydantic request/response models — shaped to grow (spec §7).

v1 fills a subset; later phases (facets, coverage, contact, match mode) add
fields WITHOUT breaking this contract. LangChain types never leak in here.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Filters(BaseModel):
    """Front-end filter selections (docling backend). Empty lists / None = no filter."""
    doc_types: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None


class QueryRequest(BaseModel):
    question: str
    backend: str = "chroma"        # "chroma" (default) | "docling" (embedding artifact)
    top_k: int | None = None       # override retrieval k; None -> config.TOP_K
    filters: Filters | None = None  # applied by the docling backend only


class Source(BaseModel):
    source_ref: str
    # optional front-end metadata (populated by the docling backend; omitted otherwise)
    doc_id: str | None = None
    doc_type: str | None = None
    page_nos: list[int] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)
    title: str | None = None
    author: str | None = None
    created: str | None = None
    modified: str | None = None
    score: float | None = None
    # enrichment fields (from app.enrich_metadata) powering the front-end filters
    technologies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    year: int | None = None
    poc_name: str | None = None
    poc_email: str | None = None
    contact_emails: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)  # empty in v1; facets/coverage/contact ride here later
    mode: str = "answer"                           # room for "match"/other modes later


class HealthResponse(BaseModel):
    ok: bool
    model: str

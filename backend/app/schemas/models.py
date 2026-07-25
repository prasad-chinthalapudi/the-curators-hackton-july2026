from datetime import date
from typing import Literal
from pydantic import BaseModel, Field

CoverageStatus = Literal["available", "partial", "missing"]

class SourceLocation(BaseModel):
    location_type: str
    location_number: int
    excerpt: str

class Coverage(BaseModel):
    executive_summary: CoverageStatus
    challenge: CoverageStatus
    solution: CoverageStatus
    technology_stack: CoverageStatus
    business_outcome: CoverageStatus
    metrics: CoverageStatus
    delivery_team: CoverageStatus
    lessons_learned: CoverageStatus

class Document(BaseModel):
    document_id: str
    file_name: str
    file_type: str
    match_score: float = 0.8
    summary: str
    tags: list[str]
    technologies: list[str]
    industry: str
    year: int
    added_on: date
    source_locations: list[SourceLocation]
    coverage: Coverage

class SearchFilters(BaseModel):
    file_types: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None

class SearchRequest(BaseModel):
    query: str = ""
    filters: SearchFilters = Field(default_factory=SearchFilters)
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)
    sort_by: str = "relevance"
    include_low_confidence: bool = False

class SelectionRequest(BaseModel):
    document_ids: list[str]

class GenerateRequest(SelectionRequest):
    title: str | None = None

class KnowledgeRequest(BaseModel):
    question: str
    answer: str
    related_document_ids: list[str]
    contributor: str

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    document_ids: list[str] = Field(default_factory=list)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)

class Citation(BaseModel):
    citation_id: str
    document_id: str
    file_name: str
    location_type: str
    location_number: int
    excerpt: str
    relevance_score: float

class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_chunk_count: int
    missing_information: list[str]
    conversation_id: str

class StructuredAnswer(BaseModel):
    answer: str
    used_citation_ids: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)

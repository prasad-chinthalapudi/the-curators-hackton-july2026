from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedRecord(BaseModel):
    doc_id: int
    document_key: str
    filename: str
    relative_path: str
    file_type: str
    raw_text: str
    text_length: int
    status: Literal["extracted"] = "extracted"


class ExtractionError(BaseModel):
    relative_path: str
    file_type: str
    error_type: str
    message: str


class ExtractionMetadata(BaseModel):
    source_directory: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_discovered: int
    total_documents: int
    total_errors: int
    extraction_complete: bool = True
    supported_file_types: list[str]


class ExtractionIndex(BaseModel):
    metadata: ExtractionMetadata
    documents: list[ExtractedRecord]
    errors: list[ExtractionError]


class ExtractionOptions(BaseModel):
    source_directory: Path
    output_file: Path
    max_files: int | None = Field(default=None, ge=1)

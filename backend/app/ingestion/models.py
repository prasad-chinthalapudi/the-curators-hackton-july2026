from pydantic import BaseModel, Field


class ExtractedDocument(BaseModel):
    doc_id: int
    filename: str
    relative_path: str
    file_type: str
    raw_text: str
    text_length: int
    status: str


class ManifestEntry(BaseModel):
    doc_id: int
    file_type: str
    reason: str


class PilotManifest(BaseModel):
    pilot_name: str
    description: str
    source_file: str
    documents: list[ManifestEntry] = Field(min_length=1)

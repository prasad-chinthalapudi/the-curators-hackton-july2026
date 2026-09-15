import json

from app.core.settings import Settings
from app.ingestion.chunker import chunk_document
from app.ingestion.models import ExtractedDocument, PilotManifest


def load_pilot_documents(config: Settings) -> list[ExtractedDocument]:
    source = json.loads(config.source_index.read_text(encoding="utf-8"))
    manifest = PilotManifest.model_validate_json(config.pilot_manifest.read_text(encoding="utf-8"))
    selected_ids = {entry.doc_id for entry in manifest.documents}
    documents = [
        ExtractedDocument.model_validate(item)
        for item in source["documents"]
        if item.get("doc_id") in selected_ids and item.get("status") == "extracted"
    ]
    found_ids = {document.doc_id for document in documents}
    missing = selected_ids - found_ids
    if missing:
        raise ValueError(f"Pilot manifest references missing document IDs: {sorted(missing)}")
    return sorted(documents, key=lambda document: document.doc_id)


def build_pilot_chunks(config: Settings):
    return [
        chunk
        for document in load_pilot_documents(config)
        for chunk in chunk_document(document, config.dataset)
    ]

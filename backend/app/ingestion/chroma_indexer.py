from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.core.settings import Settings, settings
from app.ingestion.index_loader import build_pilot_chunks


def create_vector_store(config: Settings = settings) -> Chroma:
    if not __import__("os").getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for Chroma ingestion and retrieval")
    config.chroma_directory.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=config.chroma_collection,
        persist_directory=str(config.chroma_directory),
        embedding_function=OpenAIEmbeddings(model=config.embedding_model),
        collection_metadata={"dataset": config.dataset},
    )


def ingest_pilot(config: Settings = settings) -> dict:
    chunks = build_pilot_chunks(config)
    store = create_vector_store(config)
    ids = [
        f"{chunk.metadata['document_id']}:{chunk.metadata['location_type']}:{chunk.metadata['location_number']}:{chunk.metadata['sub_chunk']}"
        for chunk in chunks
    ]
    store.add_documents(chunks, ids=ids)
    return {
        "dataset": config.dataset,
        "collection": config.chroma_collection,
        "document_count": len({chunk.metadata["document_id"] for chunk in chunks}),
        "chunk_count": len(chunks),
    }

import logging
import time
from threading import RLock

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.core.settings import Settings, settings
from app.ingestion.index_loader import build_pilot_chunks

log = logging.getLogger("pih.chroma")
_vector_stores: dict[Settings, Chroma] = {}
_vector_store_lock = RLock()


def create_vector_store(config: Settings = settings) -> Chroma:
    if not __import__("os").getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for Chroma ingestion and retrieval")
    cached = _vector_stores.get(config)
    if cached is not None:
        return cached
    with _vector_store_lock:
        cached = _vector_stores.get(config)
        if cached is not None:
            return cached
        config.chroma_directory.mkdir(parents=True, exist_ok=True)
        last_error: ValueError | KeyError | None = None
        for attempt in range(3):
            try:
                store = Chroma(
                    collection_name=config.chroma_collection,
                    persist_directory=str(config.chroma_directory),
                    embedding_function=OpenAIEmbeddings(model=config.embedding_model),
                    collection_metadata={"dataset": config.dataset},
                )
                _vector_stores[config] = store
                return store
            except (ValueError, KeyError) as error:
                is_tenant_error = "tenant default_tenant" in str(error)
                is_registry_race = isinstance(error, KeyError)
                if not is_tenant_error and not is_registry_race:
                    raise
                last_error = error
                log.warning("Chroma client initialization retry %s/3", attempt + 1)
                time.sleep(0.25 * (attempt + 1))
        raise RuntimeError(
            f"Chroma could not initialize at {config.chroma_directory}. "
            "Stop duplicate backend processes and restart the API."
        ) from last_error


def clear_vector_store_cache(config: Settings | None = None) -> None:
    with _vector_store_lock:
        if config is None:
            _vector_stores.clear()
        else:
            _vector_stores.pop(config, None)


def refresh_vector_store(config: Settings = settings) -> Chroma:
    """Reconnect to a named collection after it was replaced on disk."""
    clear_vector_store_cache(config)
    return create_vector_store(config)


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


def reset_and_ingest_pilot(config: Settings = settings) -> dict:
    store = create_vector_store(config)
    previous_chunk_count = store._collection.count()
    store.delete_collection()
    clear_vector_store_cache()
    result = ingest_pilot(config)
    result["previous_chunk_count"] = previous_chunk_count
    return result

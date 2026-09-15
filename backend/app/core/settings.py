import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _path(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else BACKEND_DIR / value


@dataclass(frozen=True)
class Settings:
    data_mode: str = os.getenv("PIH_DATA_MODE", "chroma").lower()
    source_index: Path = _path("PIH_SOURCE_INDEX", "app/extracted_data/data_extracted.txt")
    pilot_manifest: Path = _path("PIH_PILOT_MANIFEST", "app/extracted_data/pilot_manifest.json")
    chroma_directory: Path = _path("PIH_CHROMA_DIRECTORY", "app/data/chroma")
    chroma_collection: str = os.getenv("PIH_CHROMA_COLLECTION", "pih_documents")
    dataset: str = os.getenv("PIH_DATASET", "pih_initial_14")
    embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    retrieval_top_k: int = int(os.getenv("PIH_RETRIEVAL_TOP_K", "8"))
    min_relevance_score: float = float(os.getenv("PIH_MIN_RELEVANCE_SCORE", "0.40"))
    max_history_messages: int = int(os.getenv("PIH_MAX_HISTORY_MESSAGES", "8"))


settings = Settings()

"""PIH Clean Core — config: env, model resolution, paths, thresholds (spec §8)."""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("pih.config")

load_dotenv()  # OPENAI_API_KEY from .env at repo root

# --- Models (every id has a fallback; resolve at runtime, never hardcode blind) ---
EMBED_MODEL = "text-embedding-3-large"
GEN_MODEL_PRIMARY = "gpt-5.6-terra"
GEN_MODEL_FALLBACK = "gpt-5.2"

# --- Retrieval / generation knobs ---
TOP_K = 6
TEMPERATURE = 0
CHUNK_TOKENS = 700
CHUNK_OVERLAP = 100

# Grounded-assistant system prompt, shared by both backends (rag.py + retrieve_docling.py).
# Lives here so the Docling backend needs no import from the Chroma chain.
GROUNDED_SYSTEM_PROMPT = (
    "You are a grounded assistant for a Project Intelligence Hub. Answer the "
    "question using ONLY the retrieved context below. If the context does not "
    "contain the answer, say so plainly (e.g. \"I couldn't find that in the "
    "indexed documents.\") and do NOT guess or use outside knowledge. When you "
    "do answer, cite the source_ref(s) you used, in square brackets."
)

# --- Ingestion ---
MAX_FILES = 40  # dev cap; --full overrides

# --- Paths ---
UPLOADS = "data/uploads"
EXTRACTED_DIR = "data/extracted"          # phase 1: one pickle per document
CHROMA_DIR = "data/chroma"
CHROMA_COLLECTION = "chunks"
MANIFEST = "data/manifest.json"           # tracks both extract + index stages per file

# --- Docling-native embedding artifact (alt. pipeline; provenance-preserving) ---
# Single pickle of per-chunk records (text + embedding + page/heading + doc props).
# Independent of the Chroma pipeline above.
EMBED_ARTIFACT_DIR = "data/embeddings"
EMBED_ARTIFACT = "data/embeddings/docling_records.pkl"
EMBED_MAX_TOKENS = 8191                   # text-embedding-3-large context window
EMBED_BATCH = 100                         # inputs per embeddings request

# --- Frontend /api adapter (search workspace + one-pager sales brief) ---
ONEPAGER_DIR = "data/one_pagers"          # generated brief JSON + PDF, keyed by id
KNOWLEDGE_FILE = "data/knowledge.jsonl"   # appended Q&A from the "Add Knowledge" modal
ONEPAGER_MAX_SOURCE_CHARS = 24000         # cap on source text sent to the brief LLM

# --- API key ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    log.warning("OPENAI_API_KEY is not set - live API calls will fail until it is.")


# ---------------------------------------------------------------------------
# resolve_model: check the key's models once, fall back if the preferred id is
# unavailable. Guarded so importing config never crashes when offline/no key.
# ---------------------------------------------------------------------------
_AVAILABLE_MODELS: set[str] | None = None


def _available_model_ids() -> set[str]:
    global _AVAILABLE_MODELS
    if _AVAILABLE_MODELS is not None:
        return _AVAILABLE_MODELS
    _AVAILABLE_MODELS = set()
    if not OPENAI_API_KEY:
        log.warning("resolve_model: no API key; cannot query /v1/models, using preferred id as-is.")
        return _AVAILABLE_MODELS
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        _AVAILABLE_MODELS = {m.id for m in client.models.list().data}
        log.info("resolve_model: %d models available to this key.", len(_AVAILABLE_MODELS))
    except Exception as e:  # network down / bad key / SDK issue — never crash import
        log.warning("resolve_model: /v1/models check failed (%s); using preferred id as-is.", e)
        _AVAILABLE_MODELS = set()
    return _AVAILABLE_MODELS


def resolve_model(preferred: str, fallback: str | None = None) -> str:
    """Return a model id this key can actually call: prefer `preferred`, else
    `fallback` if present. If the list can't be fetched, return `preferred`."""
    available = _available_model_ids()
    if not available:
        return preferred
    if preferred in available:
        return preferred
    if fallback and fallback in available:
        log.warning("resolve_model: '%s' unavailable, falling back to '%s'.", preferred, fallback)
        return fallback
    log.warning("resolve_model: neither '%s' nor '%s' found; returning '%s' anyway.",
                preferred, fallback, preferred)
    return preferred


# Resolved generation id (computed once; safe offline).
GEN_MODEL = resolve_model(GEN_MODEL_PRIMARY, GEN_MODEL_FALLBACK)

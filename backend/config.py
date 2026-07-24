"""PIH shared config — §0 contract. Person A is the DESIGNATED EDITOR.

B and C import from here; they must NOT edit it. Changing anything in this file
means telling the other two people in the git channel first.
"""
import os
import logging

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("pih.config")

load_dotenv()  # pulls OPENAI_API_KEY from .env at repo root

# --- Models (every id has a fallback; resolve at runtime, never hardcode blind) ---
GEN_MODEL_PRIMARY = "gpt-5.6-terra"
GEN_MODEL_FALLBACK = "gpt-5.2"
ONEPAGER_MODEL = "gpt-5.6-sol"

EMBED_MODEL = "text-embedding-3-large"
EMBED_DIM = 3072

# --- Retrieval / generation knobs ---
TOP_K = 8
GROUNDED_THRESHOLD = 0.35
MATCH_THRESHOLD = 0.45
MATCH_TOP_N = 5

CHUNK_TOKENS = 700
CHUNK_OVERLAP = 100

# --- Ingestion scale guards ---
MAX_FILES = 40
MAX_IMAGES_PER_DOC = 3
MIN_IMAGE_BYTES = 8000
EMBED_BATCH = 128
CAPTION_ENABLED = True
COST_CEILING_USD = 40

# --- Paths ---
UPLOADS = "data/uploads"
IMAGES = "data/images"
LANCEDB = "data/lancedb"
GRAPH_PATH = "data/graph.json"
MANIFEST = "data/ingest_manifest.json"

# --- API key ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    log.warning("OPENAI_API_KEY is not set - live API calls (embed/chat/resolve) will fail until it is.")


# ---------------------------------------------------------------------------
# resolve_model: check the key's available models once, fall back if needed.
# Guarded so importing config never crashes B or C, even with no key/network.
# ---------------------------------------------------------------------------
_AVAILABLE_MODELS: set[str] | None = None  # cached model-id set; None = not-yet-checked


def _available_model_ids() -> set[str]:
    """Fetch GET /v1/models once and cache. Returns empty set on any failure."""
    global _AVAILABLE_MODELS
    if _AVAILABLE_MODELS is not None:
        return _AVAILABLE_MODELS
    _AVAILABLE_MODELS = set()
    if not OPENAI_API_KEY:
        log.warning("resolve_model: no API key; cannot query /v1/models, using preferred ids as-is.")
        return _AVAILABLE_MODELS
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        _AVAILABLE_MODELS = {m.id for m in client.models.list().data}
        log.info("resolve_model: %d models available to this key.", len(_AVAILABLE_MODELS))
    except Exception as e:  # network down, bad key, SDK missing — never crash import
        log.warning("resolve_model: /v1/models check failed (%s); using preferred ids as-is.", e)
        _AVAILABLE_MODELS = set()
    return _AVAILABLE_MODELS


def resolve_model(preferred: str, fallback: str | None = None) -> str:
    """Return a model id this key can actually call.

    Prefer `preferred`; if the model list was fetched and it's absent, use
    `fallback` when that one is present. If the list couldn't be fetched
    (no key/network), return `preferred` unchanged rather than guessing —
    the actual API call is still wrapped in try/except downstream.
    """
    available = _available_model_ids()
    if not available:
        return preferred  # couldn't verify — don't second-guess
    if preferred in available:
        return preferred
    if fallback and fallback in available:
        log.warning("resolve_model: '%s' unavailable, falling back to '%s'.", preferred, fallback)
        return fallback
    log.warning(
        "resolve_model: neither '%s' nor '%s' found in available models; returning '%s' anyway.",
        preferred, fallback, preferred,
    )
    return preferred


# Resolved convenience ids (computed lazily on first import; safe if offline).
GEN_MODEL = resolve_model(GEN_MODEL_PRIMARY, GEN_MODEL_FALLBACK)
ONEPAGER_MODEL_RESOLVED = resolve_model(ONEPAGER_MODEL, GEN_MODEL_FALLBACK)
EMBED_MODEL_RESOLVED = resolve_model(EMBED_MODEL, EMBED_MODEL)

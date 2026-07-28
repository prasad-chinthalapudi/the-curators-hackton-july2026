"""FastAPI app — RAG contract (/health, /query, /facets) plus the /api adapter
router (document search + one-pager sales brief) that the React frontend calls.
CORS is open for the frontend dev server.

LangChain lives inside rag.py/ingest.py; this contract stays framework-neutral.
Every handler is wrapped so a failure returns clean JSON, never a raw 500 stack.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .schemas import HealthResponse, QueryRequest, QueryResponse, Source

log = logging.getLogger("pih.main")

app = FastAPI(title="PIH Clean Core", version="1.0")

# CORS open — the React dev server (localhost:5173) calls this cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend-facing adapter (document search + one-pager sales brief) under /api.
from .api import router as api_router  # noqa: E402
app.include_router(api_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Resolve the gen model and prove the key can actually call it (live 1-token test)."""
    model = config.resolve_model(config.GEN_MODEL_PRIMARY, config.GEN_MODEL_FALLBACK)
    ok = False
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENAI_API_KEY)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        ok = True
    except Exception as e:
        log.error("/health live model check failed: %s", e)
    return HealthResponse(ok=ok, model=model)


@app.get("/facets")
def facets():
    """Distinct filter values + per-document counts for the front-end filter panel
    (doc types, technologies, industries, year range). Docling artifact only."""
    try:
        from .retrieve_docling import facets as docling_facets
        return docling_facets()
    except FileNotFoundError:
        return JSONResponse(status_code=404,
                            content={"error": "no_artifact",
                                     "detail": "run `python -m app.embed_docling --full` "
                                               "and `python -m app.enrich_metadata --full` first"})
    except Exception as e:
        log.error("/facets failed: %s", e)
        return JSONResponse(status_code=500, content={"error": "facets_failed", "detail": str(e)})


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    try:
        if req.backend == "docling":
            # Provenance-rich backend over the Docling embedding artifact.
            from .retrieve_docling import answer_query as answer_query_docling
            k = req.top_k or config.TOP_K
            filters = req.filters.model_dump() if req.filters else None
            result = answer_query_docling(req.question, k=k, filters=filters)
            sources = [Source(**s) for s in result["sources"]]  # dicts carry metadata
        else:
            # Chroma backend — imported lazily so the Docling path never loads it.
            from .rag import answer_query
            result = answer_query(req.question)
            sources = [Source(source_ref=s) for s in result["sources"]]
        return QueryResponse(
            answer=result["answer"],
            sources=sources,
            metadata={"backend": req.backend},   # facets/coverage/contact ride here later
            mode="answer",
        )
    except Exception as e:
        log.error("/query failed: %s", e)
        return JSONResponse(status_code=500, content={"error": "query_failed", "detail": str(e)})

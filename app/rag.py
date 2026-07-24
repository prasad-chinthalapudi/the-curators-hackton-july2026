"""RAG chain (spec §6) — LangChain LCEL: retrieve + generate, grounded.

Exposes one function: answer_query(question) -> {answer, sources, contexts}.
LangChain stays inside this module; the API contract never sees LC types.
"""
from __future__ import annotations

import logging

from . import config
from .ingest import get_vectorstore

log = logging.getLogger("pih.rag")

_SYSTEM = config.GROUNDED_SYSTEM_PROMPT

_chain = None


def _format_docs(docs) -> str:
    parts = []
    for d in docs:
        ref = d.metadata.get("source_ref", "unknown")
        parts.append(f"[{ref}]\n{d.page_content}")
    return "\n\n".join(parts)


def _build_chain():
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableParallel, RunnablePassthrough
    from langchain_openai import ChatOpenAI

    retriever = get_vectorstore().as_retriever(search_kwargs={"k": config.TOP_K})
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ])
    llm = ChatOpenAI(
        model=config.resolve_model(config.GEN_MODEL_PRIMARY, config.GEN_MODEL_FALLBACK),
        temperature=config.TEMPERATURE,
        api_key=config.OPENAI_API_KEY,
    )

    # Retrieve docs once, KEEP them alongside the generated answer (don't collapse).
    generate = (
        RunnablePassthrough.assign(context=lambda x: _format_docs(x["docs"]))
        | prompt
        | llm
        | StrOutputParser()
    )
    return RunnableParallel(
        {"docs": retriever, "question": RunnablePassthrough()}
    ).assign(answer=generate)


def get_chain():
    global _chain
    if _chain is None:
        _chain = _build_chain()
    return _chain


def answer_query(question: str) -> dict:
    """Return {answer, sources, contexts}. sources = source_refs used;
    contexts = retrieved chunk texts (debug/future). Never raises."""
    try:
        out = get_chain().invoke(question)
    except Exception as e:
        log.error("answer_query failed: %s", e)
        return {"answer": "The query pipeline hit an error and could not produce an answer.",
                "sources": [], "contexts": []}
    docs = out.get("docs", [])
    seen, sources = set(), []
    for d in docs:
        ref = d.metadata.get("source_ref", "unknown")
        if ref not in seen:
            seen.add(ref)
            sources.append(ref)
    return {"answer": out.get("answer", ""), "sources": sources,
            "contexts": [d.page_content for d in docs]}

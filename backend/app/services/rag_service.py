import logging
import os
from uuid import uuid4

from langchain_openai import ChatOpenAI

from app.core.settings import Settings, settings
from app.retrieval.retriever import RetrievedChunk, retrieve_chunks
from app.schemas.models import (
    ChatRequest,
    ChatResponse,
    Citation,
    StructuredAnswer,
)

log = logging.getLogger("pih.rag")

SYSTEM_PROMPT = """You are the grounded assistant for Project Intelligence Hub.
Answer using ONLY the supplied retrieved evidence. Never use outside knowledge.
If the evidence does not contain the answer, say so plainly and list what is
missing. Cite claims using only the exact citation IDs supplied with the
evidence. Return only citations that materially support your answer."""


class RetrievalUnavailableError(RuntimeError):
    pass


class GenerationUnavailableError(RuntimeError):
    pass


def _format_evidence(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for chunk in chunks:
        metadata = chunk.document.metadata
        blocks.append(
            f"[CITATION {chunk.citation_id}]\n"
            f"File: {metadata['file_name']}\n"
            f"Location: {metadata['location_type']} {metadata['location_number']}\n"
            f"Relevance: {chunk.relevance_score:.3f}\n"
            f"Content:\n{chunk.document.page_content}"
        )
    return "\n\n".join(blocks)


def _citation(chunk: RetrievedChunk) -> Citation:
    metadata = chunk.document.metadata
    return Citation(
        citation_id=chunk.citation_id,
        document_id=str(metadata["document_id"]),
        file_name=str(metadata["file_name"]),
        location_type=str(metadata["location_type"]),
        location_number=int(metadata["location_number"]),
        excerpt=chunk.document.page_content[:320].strip(),
        relevance_score=round(chunk.relevance_score, 4),
    )


def answer_query(request: ChatRequest, config: Settings = settings) -> ChatResponse:
    conversation_id = request.conversation_id or f"conversation_{uuid4().hex[:12]}"
    try:
        chunks = retrieve_chunks(request.message, request.filters, request.document_ids, config)
    except Exception as error:
        log.exception("Retrieval failed")
        raise RetrievalUnavailableError("Document retrieval is currently unavailable") from error

    if not chunks:
        return ChatResponse(
            answer="I couldn't find that in the indexed documents.",
            citations=[],
            retrieved_chunk_count=0,
            missing_information=["No chunks met the configured relevance and metadata criteria."],
            conversation_id=conversation_id,
        )
    if not os.getenv("OPENAI_API_KEY"):
        raise GenerationUnavailableError("OPENAI_API_KEY is not configured")

    bounded_history = request.history[-config.max_history_messages:]
    history_text = "\n".join(
        f"{message.role.upper()}: {message.content}" for message in bounded_history
    ) or "No previous conversation."
    user_prompt = (
        f"Conversation history:\n{history_text}\n\n"
        f"Retrieved evidence:\n{_format_evidence(chunks)}\n\n"
        f"Current question: {request.message}"
    )
    try:
        model = ChatOpenAI(model=config.chat_model, api_key=os.getenv("OPENAI_API_KEY"))
        structured_model = model.with_structured_output(StructuredAnswer, method="json_schema")
        result = structured_model.invoke([
            ("system", SYSTEM_PROMPT),
            ("human", user_prompt),
        ])
    except Exception as error:
        log.exception("Grounded generation failed")
        raise GenerationUnavailableError("Answer generation is currently unavailable") from error

    by_id = {chunk.citation_id: chunk for chunk in chunks}
    citations = [
        _citation(by_id[citation_id])
        for citation_id in result.used_citation_ids
        if citation_id in by_id
    ]
    return ChatResponse(
        answer=result.answer,
        citations=citations,
        retrieved_chunk_count=len(chunks),
        missing_information=result.missing_information,
        conversation_id=conversation_id,
    )

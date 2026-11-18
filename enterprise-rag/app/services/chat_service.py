"""Permission-safe RAG chat orchestration and persistence."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime

try:
    from datetime import UTC
except ImportError:  # pragma: no cover - Python < 3.11 compatibility
    from datetime import timezone

    UTC = timezone.utc
from uuid import UUID

from fastapi import HTTPException, status
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.identity import Principal
from app.core.logging import log_event
from app.integrations.llm.factory import create_llm_generator
from app.models import Citation, Conversation, Message, UsageRecord
from app.models.mixins import uuid7
from app.rag.embeddings.base import EmbeddingProviderError
from app.rag.generators.base import LLMProviderError
from app.rag.generators.llm_generator import generate_answer
from app.rag.prompts.rag_prompt import build_rag_prompt
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.citation import CitationResponse
from app.schemas.requests import ChatRequest
from app.services.retrieval_service import retrieve_evidence

logger = logging.getLogger("app.chat")

INSUFFICIENT_EVIDENCE = (
    "I could not find authorized indexed evidence to answer this question."
    )


@dataclass(frozen=True, slots=True)
class ChatTurn:
    conversation: Conversation
    user_message: Message
    assistant_message: Message
    answer: str
    citations: list[CitationResponse]
    status: str
    confidence: float | None = None


async def answer_from_available_sources(
    session: AsyncSession,
    body: ChatRequest,
    principal: Principal,
    qdrant: AsyncQdrantClient,
) -> ChatTurn:
    if "chat:ask" not in principal.permissions and not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Chat permission required"
        )
    repository = ConversationRepository(session)
    if body.conversation_id:
        conversation = await repository.find_active_owned(
            body.conversation_id, principal.organization_id, principal.user.id
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            id=uuid7(),
            organization_id=principal.organization_id,
            user_id=principal.user.id,
            title=body.question[:255],
            status="active",
        )

    try:
        evidence = await retrieve_evidence(session, qdrant, principal, body.question)
    except EmbeddingProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval is currently unavailable",
        ) from exc
    await repository.commit()
    citations: list[CitationResponse] = []
    citation_records: list[Citation] = []
    answer_text = INSUFFICIENT_EVIDENCE
    answer_status = "insufficient_evidence"
    confidence = None
    model_name = None
    usage: UsageRecord | None = None

    if evidence:
        try:
            generator = create_llm_generator()
            prompt = build_rag_prompt(
                body.question,
                evidence,
                context_token_limit=settings.rag.context_token_limit,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The question exceeds the configured model context budget",
            ) from exc
        except LLMProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Grounded answer generation is currently unavailable",
            ) from exc
        started = time.perf_counter()
        try:
            generated = await generate_answer(generator, prompt)
        except LLMProviderError as exc:
            log_event(
                logger,
                logging.ERROR,
                "Grounded answer generation failed",
                operation="llm.generate",
                provider=getattr(generator, "provider", None),
                model=getattr(generator, "model_name", None),
                duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
                error_code="LLM_PROVIDER_ERROR",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Grounded answer generation is currently unavailable",
            ) from exc
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        model_name = generator.model_name
        answer_status = generated.status
        answer_text = generated.answer
        confidence = generated.confidence

        evidence_by_id = {
            chunk.chunk_id: chunk
            for chunk in evidence
            if chunk.chunk_id is not None and chunk.chunk_id in prompt.source_ids
        }
        cited_ids = list(dict.fromkeys(generated.citation_ids))
        if generated.status == "answered" and (
            not cited_ids
            or any(citation_id not in evidence_by_id for citation_id in cited_ids)
        ):
            answer_status = "insufficient_evidence"
            answer_text = INSUFFICIENT_EVIDENCE
            confidence = None
            cited_ids = []
        elif generated.status != "answered":
            cited_ids = []

        for citation_id in cited_ids:
            chunk = evidence_by_id[citation_id]
            document_id = UUID(chunk.document_id)
            chunk_id = UUID(citation_id)
            title = chunk.document_title or "Source document"
            excerpt = chunk.text[:1200]
            citations.append(
                CitationResponse(
                    document_id=document_id,
                    document_title=title,
                    chunk_id=chunk_id,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    excerpt=excerpt,
                    score=chunk.score,
                )
            )
            citation_records.append(
                Citation(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    excerpt=excerpt,
                    score=chunk.score,
                )
            )
        usage = UsageRecord(
            organization_id=principal.organization_id,
            user_id=principal.user.id,
            resource_type="chat",
            model_name=generator.model_name,
            provider=generator.provider,
            input_tokens=max(
                1, (len(prompt.system) + len(prompt.user)) // 3
            ),
            output_tokens=max(1, len(answer_text) // 4),
            latency_ms=latency_ms,
        )

    user_message = Message(
        conversation_id=conversation.id, role="user", content=body.question
    )
    conversation.updated_at = datetime.now(UTC)
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_text,
        model_name=model_name,
    )
    await repository.persist_chat_turn(
        conversation,
        user_message,
        assistant_message,
        citations=citation_records,
        usage=usage,
    )
    return ChatTurn(
        conversation=conversation,
        user_message=user_message,
        assistant_message=assistant_message,
        answer=answer_text,
        citations=citations,
        status=answer_status,
        confidence=confidence,
    )

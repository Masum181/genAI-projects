"""Grounded chat and SSE endpoints."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    Principal,
    get_current_principal,
    get_db,
    get_qdrant_client,
)
from app.api.v1.common import response
from app.schemas.requests import ChatRequest
from app.services.chat_service import ChatTurn, answer_from_available_sources

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=None)
async def ask_question(
    body: ChatRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> dict | StreamingResponse:
    turn = await answer_from_available_sources(db, body, principal, qdrant)
    if body.stream:
        return _stream_response(turn, request)
    return response(
        request,
        {
            "conversation_id": str(turn.conversation.id),
            "user_message_id": str(turn.user_message.id),
            "message_id": str(turn.assistant_message.id),
            "answer": turn.answer,
            "citations": [
                citation.model_dump(mode="json") for citation in turn.citations
            ],
            "status": turn.status,
            "confidence": turn.confidence,
        },
    )


@router.post("/chat/stream")
async def stream_answer(
    body: ChatRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> StreamingResponse:
    turn = await answer_from_available_sources(db, body, principal, qdrant)
    return _stream_response(turn, request)


def _stream_response(turn: ChatTurn, request: Request) -> StreamingResponse:
    request_id = getattr(request.state, "request_id", "unknown")

    async def events() -> AsyncIterator[str]:
        answer = turn.answer
        for start in range(0, len(answer), 80):
            token_data = {
                "conversation_id": str(turn.conversation.id),
                "request_id": request_id,
                "message_id": str(turn.assistant_message.id),
                "token": answer[start : start + 80],
            }
            payload = json.dumps(token_data, ensure_ascii=False)
            yield f"event: token\ndata: {payload}\n\n"
        end_data = {
            "conversation_id": str(turn.conversation.id),
            "request_id": request_id,
            "message_id": str(turn.assistant_message.id),
            "status": turn.status,
            "citations": [
                citation.model_dump(mode="json") for citation in turn.citations
            ],
            "confidence": turn.confidence,
        }
        yield f"event: end\ndata: {json.dumps(end_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

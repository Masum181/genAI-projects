"""Conversation creation, listing, and history endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Principal, get_current_principal, get_db
from app.api.v1.common import response
from app.schemas.requests import ConversationUpdate
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    request: Request,
    page: int = 1,
    page_size: int = 25,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return response(
        request,
        await conversation_service.list_conversations(db, principal, page, page_size),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: Request,
    title: str | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await conversation_service.create_conversation(db, principal, title)
    return response(request, data)


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await conversation_service.get_conversation(db, principal, conversation_id)
    return response(request, data)


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: UUID,
    body: ConversationUpdate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await conversation_service.update_conversation(
        db, principal, conversation_id, body
    )
    return response(request, data)

"""Conversation ownership, persistence, and history use cases."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import Principal
from app.models import Conversation
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.requests import ConversationUpdate
from app.services.common import paginate_statement, serialize_model


def _require_history_permission(principal: Principal) -> None:
    if "chat:history_view" not in principal.permissions and not principal.is_admin:
        raise HTTPException(
            status_code=403, detail="Conversation history permission required"
        )


async def list_conversations(
    session: AsyncSession, principal: Principal, page: int, page_size: int
) -> dict:
    _require_history_permission(principal)
    repository = ConversationRepository(session)
    return await paginate_statement(
        session,
        repository.for_user(principal.organization_id, principal.user.id),
        page=page,
        page_size=page_size,
        order_column=Conversation.updated_at,
    )


async def dashboard_conversation_count(
    session: AsyncSession, principal: Principal
) -> int:
    _require_history_permission(principal)
    return await ConversationRepository(session).count_for_user(
        principal.organization_id, principal.user.id
    )


async def recent_conversations(
    session: AsyncSession, principal: Principal, limit: int = 100
) -> list[Conversation]:
    _require_history_permission(principal)
    return await ConversationRepository(session).recent_for_user(
        principal.organization_id, principal.user.id, limit
    )


async def create_conversation(
    session: AsyncSession, principal: Principal, title: str | None
) -> dict:
    _require_history_permission(principal)
    repository = ConversationRepository(session)
    conversation = Conversation(
        organization_id=principal.organization_id,
        user_id=principal.user.id,
        title=title[:255] if title else None,
        status="active",
    )
    await repository.add(conversation)
    await repository.commit()
    await repository.refresh(conversation)
    return serialize_model(conversation)


async def get_conversation(
    session: AsyncSession, principal: Principal, conversation_id: UUID
) -> dict:
    _require_history_permission(principal)
    repository = ConversationRepository(session)
    conversation = await repository.find_owned(
        conversation_id, principal.organization_id, principal.user.id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await repository.get_messages(conversation.id)
    citations = await repository.citations_for([message.id for message in messages])
    citations_by_message: dict[UUID, list[dict]] = {}
    for citation in citations:
        citations_by_message.setdefault(citation.message_id, []).append(
            serialize_model(citation)
        )
    result = serialize_model(conversation)
    result["messages"] = []
    for message in messages:
        message_data = serialize_model(message)
        message_data["citations"] = citations_by_message.get(message.id, [])
        result["messages"].append(message_data)
    return result


async def update_conversation(
    session: AsyncSession,
    principal: Principal,
    conversation_id: UUID,
    changes: ConversationUpdate,
) -> dict:
    _require_history_permission(principal)
    repository = ConversationRepository(session)
    conversation = await repository.find_owned(
        conversation_id, principal.organization_id, principal.user.id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    for key, value in changes.model_dump(exclude_unset=True).items():
        setattr(conversation, key, value)
    conversation = await repository.save(conversation)
    return serialize_model(conversation)

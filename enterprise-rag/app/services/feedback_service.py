"""Feedback capture and review workflow use cases."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import Principal
from app.models import Feedback
from app.repositories.message_repository import MessageRepository
from app.schemas.requests import FeedbackCreate
from app.services.common import serialize_model


async def submit_feedback(
    session: AsyncSession, principal: Principal, body: FeedbackCreate
) -> dict:
    if "feedback:create" not in principal.permissions and not principal.is_admin:
        raise HTTPException(status_code=403, detail="Feedback permission required")
    repository = MessageRepository(session)
    conversation = await repository.find_owned_conversation(
        body.conversation_id, principal.organization_id, principal.user.id
    )
    message = await repository.find_answer(body.message_id, body.conversation_id)
    if conversation is None or message is None or message.role != "assistant":
        raise HTTPException(status_code=404, detail="Answer not found")
    feedback = Feedback(
        organization_id=principal.organization_id,
        user_id=principal.user.id,
        conversation_id=body.conversation_id,
        message_id=body.message_id,
        feedback_type=body.feedback_type,
        note=body.note,
    )
    await repository.add(feedback)
    await repository.commit()
    await repository.refresh(feedback)
    return serialize_model(feedback)


async def get_feedback(
    session: AsyncSession, principal: Principal, feedback_id: UUID
) -> dict:
    feedback = await MessageRepository(session).find_user_feedback(
        feedback_id, principal.organization_id, principal.user.id
    )
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return serialize_model(feedback)

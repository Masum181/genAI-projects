"""PostgreSQL repository for messages, citations, and feedback records."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Feedback, Message
from app.repositories.base import SQLAlchemyRepository


class MessageRepository(SQLAlchemyRepository):
    async def find_owned_conversation(
        self, conversation_id: UUID, organization_id: UUID, user_id: UUID
    ) -> Conversation | None:
        return await self.one_or_none(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.organization_id == organization_id,
                Conversation.user_id == user_id,
            )
        )

    async def find_answer(
        self, message_id: UUID, conversation_id: UUID
    ) -> Message | None:
        return await self.one_or_none(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation_id,
            )
        )

    async def find_user_feedback(
        self, feedback_id: UUID, organization_id: UUID, user_id: UUID
    ) -> Feedback | None:
        return await self.one_or_none(
            select(Feedback).where(
                Feedback.id == feedback_id,
                Feedback.organization_id == organization_id,
                Feedback.user_id == user_id,
            )
        )


def message_repository(session: AsyncSession) -> MessageRepository:
    return MessageRepository(session)

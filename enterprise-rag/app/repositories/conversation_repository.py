"""PostgreSQL repository for conversation ownership and lifecycle."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Citation, Conversation, Document, Message, UsageRecord
from app.repositories.base import SQLAlchemyRepository


class ConversationRepository(SQLAlchemyRepository):
    async def find_owned(
        self, conversation_id: UUID, organization_id: UUID, user_id: UUID
    ) -> Conversation | None:
        return await self.one_or_none(
            self.owned_by(conversation_id, organization_id, user_id)
        )

    def owned_by(self, conversation_id: UUID, organization_id: UUID, user_id: UUID):
        return select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id,
            Conversation.user_id == user_id,
        )

    def for_user(self, organization_id: UUID, user_id: UUID):
        return select(Conversation).where(
            Conversation.organization_id == organization_id,
            Conversation.user_id == user_id,
        )

    async def get_messages(self, conversation_id: UUID) -> list[Message]:
        return await self.all(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        )

    async def citations_for(self, message_ids: list[UUID]) -> list[Citation]:
        if not message_ids:
            return []
        return await self.all(
            select(Citation).where(Citation.message_id.in_(message_ids))
        )

    async def find_active_owned(
        self, conversation_id: UUID, organization_id: UUID, user_id: UUID
    ) -> Conversation | None:
        return await self.one_or_none(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.organization_id == organization_id,
                Conversation.user_id == user_id,
                Conversation.status == "active",
            )
        )

    async def count_indexed_documents(self, organization_id: UUID) -> int:
        from sqlalchemy import func

        return int(
            await self.scalar(
                select(func.count(Document.id)).where(
                    Document.organization_id == organization_id,
                    Document.status == "indexed",
                    Document.deleted_at.is_(None),
                )
            )
            or 0
        )

    async def append_messages(self, messages: list[Message]) -> None:
        await self.add_all(messages)
        await self.commit()

    async def persist_chat_turn(
        self,
        conversation: Conversation,
        user_message: Message,
        assistant_message: Message,
        *,
        citations: list[Citation],
        usage: UsageRecord | None,
    ) -> None:
        self.session.add_all([conversation, user_message, assistant_message])
        await self.flush()
        for citation in citations:
            citation.message_id = assistant_message.id
        self.session.add_all(citations)
        if usage is not None:
            usage.resource_id = assistant_message.id
            self.session.add(usage)
        await self.commit()
        await self.refresh(conversation)
        await self.refresh(user_message)
        await self.refresh(assistant_message)

    async def count_for_user(self, organization_id: UUID, user_id: UUID) -> int:
        return int(
            await self.scalar(
                select(func.count(Conversation.id)).where(
                    Conversation.organization_id == organization_id,
                    Conversation.user_id == user_id,
                )
            )
            or 0
        )

    async def recent_for_user(
        self, organization_id: UUID, user_id: UUID, limit: int
    ) -> list[Conversation]:
        return await self.all(
            self.for_user(organization_id, user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )

    async def save(self, conversation: Conversation) -> Conversation:
        await self.commit()
        await self.refresh(conversation)
        return conversation


def conversation_repository(session: AsyncSession) -> ConversationRepository:
    return ConversationRepository(session)

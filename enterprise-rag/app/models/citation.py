"""Verifiable link from a generated answer to document evidence."""

from uuid import UUID

from sqlalchemy import DOUBLE_PRECISION, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class Citation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "citations"

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL")
    )
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(255))
    excerpt: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(DOUBLE_PRECISION)

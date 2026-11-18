"""Explicit document-level access grant or denial model."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class DocumentPermission(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "document_permissions"
    __table_args__ = (
        CheckConstraint(
            "permission IN ('read', 'write', 'admin', 'deny')",
            name="ck_document_permissions_permission",
        ),
        Index(
            "ix_document_permissions_doc_dept_user",
            "document_id",
            "department_id",
            "user_id",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    permission: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'read'")
    )
    grant_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'department'")
    )

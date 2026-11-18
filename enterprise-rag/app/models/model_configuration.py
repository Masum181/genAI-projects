"""Tenant-specific or platform-wide LLM model configuration."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class ModelConfiguration(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "model_configurations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "model_name",
            name="uq_model_configurations_org_provider_model",
        ),
    )

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'chat'")
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    is_default: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )

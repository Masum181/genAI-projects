"""Association of a user with a department."""

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class DepartmentMember(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "department_members"
    __table_args__ = (
        UniqueConstraint("department_id", "user_id", name="uq_department_members"),
    )

    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'member'")
    )

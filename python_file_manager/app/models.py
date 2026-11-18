import uuid

from sqlalchemy import (
    String,
    DateTime,
    Integer,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    filename: Mapped[str] = mapped_column(String(255))

    object_name: Mapped[str] = mapped_column(
        String(500),
        unique=True
    )

    file_size: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded"
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )


    
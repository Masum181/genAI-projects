"""Validated API request bodies shared across endpoint modules."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    organization_slug: str | None = None


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=255)
    organization_slug: str = Field(
        min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$"
    )
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: Password


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class APIKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scopes: list[str] = Field(min_length=1, max_length=100)
    expires_at: datetime | None = None


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    settings: dict[str, Any] = Field(default_factory=dict)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    settings: dict[str, Any] | None = None
    status: Literal["active", "suspended"] | None = None


class UserInvite(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: Literal["employee", "department_manager", "organization_admin"] = "employee"
    department_id: UUID | None = None


class AcceptInviteRequest(BaseModel):
    invitation_token: str = Field(min_length=20, max_length=256)
    password: Password


class UserStatusUpdate(BaseModel):
    status: Literal["active", "disabled"]


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_department_id: UUID | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_department_id: UUID | None = None


class DocumentMetadataUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    department_id: UUID | None = None
    document_type: str | None = Field(default=None, max_length=64)


class DocumentPermissionInput(BaseModel):
    department_id: UUID | None = None
    user_id: UUID | None = None
    permission: Literal["read", "write", "admin", "deny"] = "read"
    grant_type: Literal["department", "user", "organization"] = "department"


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    question: str = Field(min_length=1, max_length=20_000)
    stream: bool = False

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        question = " ".join(value.split())
        if not question:
            raise ValueError("Question must contain non-whitespace characters")
        return question


class FeedbackCreate(BaseModel):
    conversation_id: UUID
    message_id: UUID
    feedback_type: Literal[
        "thumbs_up", "thumbs_down", "incorrect", "hallucination", "missing_context"
    ]
    note: str | None = Field(default=None, max_length=10_000)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    status: Literal["active", "archived", "closed"] | None = None


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UploadAccepted(BaseModel):
    document_id: UUID
    ingestion_job_id: UUID
    status: str


class TimestampFilter(BaseModel):
    start_at: datetime | None = None
    end_at: datetime | None = None

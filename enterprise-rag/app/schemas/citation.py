"""Citation response shape backed by persisted source records."""

from uuid import UUID

from pydantic import BaseModel


class CitationResponse(BaseModel):
    document_id: UUID
    document_title: str
    chunk_id: UUID
    page_number: int | None = None
    section_title: str | None = None
    excerpt: str
    score: float

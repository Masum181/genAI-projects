"""Provider-neutral retrieval result and authorization-aware interface."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    """Server-resolved tenant and document scope required for retrieval.

    An empty ``document_ids`` tuple means that no documents are authorized.
    Implementations must not interpret it as an unrestricted search.
    """

    organization_id: str
    document_ids: tuple[str, ...]
    version_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A retrieved chunk and its source metadata, before LLM context use."""

    document_id: str
    text: str
    score: float
    page_number: int | None = None
    chunk_id: str | None = None
    document_title: str | None = None
    section_title: str | None = None
    version_id: str | None = None
    token_count: int | None = None


class Retriever(Protocol):
    """Contract requiring explicit authorized scope for every search."""

    async def search(
        self, query: str, *, scope: RetrievalScope, limit: int
    ) -> list[RetrievedChunk]:
        """Return only chunks allowed by the server-resolved retrieval scope."""

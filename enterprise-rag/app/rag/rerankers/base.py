"""Provider-neutral interface for reranking retrieved chunks."""

from typing import Protocol

from app.rag.retrievers.base import RetrievedChunk


class Reranker(Protocol):
    """Contract for ordering candidate chunks by query relevance."""

    async def rerank(
        self, query: str, candidates: list[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        """Return candidates ordered by reranked relevance."""

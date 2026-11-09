"""Provider-neutral interface for generating dense text embeddings."""

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Contract for embedding providers with a consistent vector dimension."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed an ordered batch of document chunks."""

    async def embed_query(self, text: str) -> list[float]:
        """Embed one user query in the same vector space."""

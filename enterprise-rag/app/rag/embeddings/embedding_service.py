"""Construct the configured embedding provider."""

from app.core.config import settings
from app.rag.embeddings.base import EmbeddingProvider, EmbeddingProviderError
from app.rag.embeddings.providers import SentenceTransformerEmbeddingProvider


def create_embedding_provider() -> EmbeddingProvider:
    """Return a provider whose vectors match the configured Qdrant collection."""
    if settings.embedding.provider == "sentence_transformers":
        return SentenceTransformerEmbeddingProvider()
    raise EmbeddingProviderError(
        f"Unsupported embedding provider: {settings.embedding.provider!r}"
    )

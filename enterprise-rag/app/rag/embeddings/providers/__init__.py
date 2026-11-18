"""Concrete embedding provider implementations."""

from app.rag.embeddings.providers.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)

__all__ = ["SentenceTransformerEmbeddingProvider"]

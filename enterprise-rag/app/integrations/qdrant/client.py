"""Factory for the shared Qdrant client."""

from qdrant_client import QdrantClient

from app.core.config import settings


def create_qdrant_client() -> QdrantClient:
    """Create a Qdrant client using centralized connection settings."""
    return QdrantClient(
        url=settings.qdrant.url,
        api_key=settings.qdrant.api_key,
    )

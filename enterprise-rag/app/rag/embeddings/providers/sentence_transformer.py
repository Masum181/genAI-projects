"""Local Sentence Transformers embedding provider."""

import asyncio
from functools import lru_cache

from app.core.config import settings
from app.rag.embeddings.base import EmbeddingProviderError


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingProviderError(
            "Sentence Transformers is required for document indexing; "
            "install the project's AI extra"
        ) from exc
    return SentenceTransformer(settings.embedding.model_name)


def _encode(texts: list[str]):
    return _load_model().encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


class SentenceTransformerEmbeddingProvider:
    """Generate vectors with the configured local Sentence Transformers model."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = await asyncio.to_thread(_encode, texts)
        return vectors.tolist()

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_documents([text])
        return vectors[0]

"""Batch cross-encoder reranking for permission-verified candidates."""

import asyncio
from functools import lru_cache

from app.core.config import settings
from app.rag.embeddings.base import EmbeddingProviderError
from app.rag.retrievers.base import RetrievedChunk


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise EmbeddingProviderError(
            "Sentence Transformers is required for RAG reranking; "
            "install the project's AI extra"
        ) from exc
    return CrossEncoder(settings.rag.reranker_model_name)


def _predict(query: str, candidates: list[RetrievedChunk]) -> list[float]:
    pairs = [(query, candidate.text) for candidate in candidates]
    return [float(score) for score in _load_model().predict(pairs)]


class CrossEncoderReranker:
    """Reorder evidence by joint query/passage relevance."""

    async def rerank(
        self, query: str, candidates: list[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        if len(candidates) < 2:
            return candidates
        scores = await asyncio.to_thread(_predict, query, candidates)
        if len(scores) != len(candidates):
            raise ValueError("Reranker returned an unexpected number of scores")
        reranked = [
            RetrievedChunk(
                document_id=chunk.document_id,
                text=chunk.text,
                score=score,
                page_number=chunk.page_number,
                chunk_id=chunk.chunk_id,
                document_title=chunk.document_title,
                section_title=chunk.section_title,
                version_id=chunk.version_id,
                token_count=chunk.token_count,
            )
            for chunk, score in zip(candidates, scores, strict=True)
        ]
        return sorted(
            reranked, key=lambda item: (-item.score, item.chunk_id or "")
        )

"""Reciprocal-rank fusion for dense and sparse candidate lists."""

from app.rag.retrievers.base import RetrievedChunk


def reciprocal_rank_fusion(
    rankings: list[list[RetrievedChunk]], *, limit: int, rank_constant: int = 60
) -> list[RetrievedChunk]:
    """Merge ranked lists without allowing raw provider scores to dominate."""
    if limit < 1 or rank_constant < 1:
        raise ValueError("Fusion limit and rank constant must be positive")

    scores: dict[str, float] = {}
    chunks: dict[str, RetrievedChunk] = {}
    for ranking in rankings:
        seen_in_ranking: set[str] = set()
        rank = 0
        for chunk in ranking:
            if not chunk.chunk_id or chunk.chunk_id in seen_in_ranking:
                continue
            rank += 1
            seen_in_ranking.add(chunk.chunk_id)
            chunks.setdefault(chunk.chunk_id, chunk)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + (
                1.0 / (rank_constant + rank)
            )

    fused = [
        RetrievedChunk(
            document_id=chunk.document_id,
            text=chunk.text,
            score=scores[chunk_id],
            page_number=chunk.page_number,
            chunk_id=chunk.chunk_id,
            document_title=chunk.document_title,
            section_title=chunk.section_title,
            version_id=chunk.version_id,
            token_count=chunk.token_count,
        )
        for chunk_id, chunk in chunks.items()
    ]
    return sorted(fused, key=lambda item: (-item.score, item.chunk_id or ""))[:limit]

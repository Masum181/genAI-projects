"""Permission-filtered hybrid retrieval and verified evidence selection."""

import unicodedata
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.identity import Principal
from app.rag.embeddings.embedding_service import create_embedding_provider
from app.rag.rerankers.cross_encoder_reranker import CrossEncoderReranker
from app.rag.retrievers.base import RetrievalScope, RetrievedChunk
from app.rag.retrievers.dense_retriever import DenseRetriever
from app.rag.retrievers.hybrid_retriever import reciprocal_rank_fusion
from app.rag.retrievers.sparse_retriever import SparseRetriever
from app.repositories.document_repository import DocumentRepository


def normalize_query(query: str) -> str:
    """Normalize whitespace and Unicode without changing query semantics."""
    return " ".join(unicodedata.normalize("NFKC", query).split())


async def retrieve_evidence(
    session: AsyncSession,
    qdrant: AsyncQdrantClient,
    principal: Principal,
    question: str,
) -> list[RetrievedChunk]:
    """Retrieve, fuse, and rerank only current chunks the principal may read."""
    repository = DocumentRepository(session)
    document_versions = await repository.authorized_indexed_versions(
        principal.organization_id,
        principal.user.id,
        is_admin=principal.is_admin,
    )
    if not document_versions:
        return []

    scope = RetrievalScope(
        organization_id=str(principal.organization_id),
        document_ids=tuple(str(document_id) for document_id, _ in document_versions),
        version_ids=tuple(str(version_id) for _, version_id in document_versions),
    )
    query = normalize_query(question)
    if not query:
        return []

    embedder = create_embedding_provider()
    dense = await DenseRetriever(qdrant, embedder).search(
        query, scope=scope, limit=settings.rag.candidate_limit
    )
    sparse = await SparseRetriever(
        repository,
        principal.organization_id,
        principal.user.id,
        is_admin=principal.is_admin,
    ).search(
        query, scope=scope, limit=settings.rag.candidate_limit
    )
    fused = reciprocal_rank_fusion(
        [dense, sparse], limit=settings.rag.candidate_limit
    )
    if not fused:
        return []

    chunk_ids = [UUID(chunk.chunk_id) for chunk in fused if chunk.chunk_id]
    verified_rows = await repository.authorized_chunks_by_ids(
        principal.organization_id,
        principal.user.id,
        is_admin=principal.is_admin,
        chunk_ids=chunk_ids,
    )
    fused_scores = {candidate.chunk_id: candidate.score for candidate in fused}
    verified_by_id = {}
    for chunk, title in verified_rows:
        verified_by_id[str(chunk.id)] = RetrievedChunk(
            document_id=str(chunk.document_id),
            text=chunk.content,
            score=fused_scores[str(chunk.id)],
            page_number=chunk.page_number,
            chunk_id=str(chunk.id),
            document_title=title,
            section_title=chunk.section_title
            or chunk.chunk_metadata.get("section_title"),
            version_id=str(chunk.version_id),
            token_count=chunk.token_count,
        )
    candidates = [
        verified_by_id[candidate.chunk_id]
        for candidate in fused
        if candidate.chunk_id in verified_by_id
    ]
    if not candidates:
        return []

    reranked = await CrossEncoderReranker().rerank(query, candidates)
    return reranked[: settings.rag.result_limit]

"""Dense vector retrieval restricted by server-resolved document permissions."""

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings
from app.integrations.qdrant.collections import DOCUMENT_CHUNKS_COLLECTION
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.retrievers.base import RetrievalScope, RetrievedChunk


class DenseRetriever:
    """Search active Qdrant points only within an authorized tenant/document set."""

    def __init__(
        self, client: AsyncQdrantClient, embedding_provider: EmbeddingProvider
    ) -> None:
        self.client = client
        self.embedding_provider = embedding_provider

    async def search(
        self, query: str, *, scope: RetrievalScope, limit: int
    ) -> list[RetrievedChunk]:
        if not scope.document_ids or not scope.version_ids or limit < 1:
            return []
        vector = await self.embedding_provider.embed_query(query)
        if len(vector) != settings.embedding.dimensions:
            raise ValueError(
                f"Query embedding dimension {len(vector)} does not match configured "
                f"dimension {settings.embedding.dimensions}"
            )
        response = await self.client.query_points(
            collection_name=DOCUMENT_CHUNKS_COLLECTION,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="organization_id",
                        match=models.MatchValue(value=scope.organization_id),
                    ),
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchAny(any=list(scope.document_ids)),
                    ),
                    models.FieldCondition(
                        key="document_version_id",
                        match=models.MatchAny(any=list(scope.version_ids)),
                    ),
                    models.FieldCondition(
                        key="is_deleted",
                        match=models.MatchValue(value=False),
                    ),
                ]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        results = []
        for point in response.points:
            payload = point.payload or {}
            results.append(
                RetrievedChunk(
                    document_id=str(payload.get("document_id", "")),
                    text=str(payload.get("text", "")),
                    score=float(point.score),
                    page_number=payload.get("page_number"),
                    chunk_id=str(point.id),
                    document_title=payload.get("source_title"),
                    section_title=payload.get("section_title"),
                    version_id=payload.get("document_version_id"),
                    token_count=payload.get("token_count"),
                )
            )
        return results

"""PostgreSQL full-text retrieval using the same tenant and ACL filters."""

from uuid import UUID

from app.rag.retrievers.base import RetrievalScope, RetrievedChunk
from app.repositories.document_repository import DocumentRepository


class SparseRetriever:
    """Retrieve lexical matches from authoritative current chunk records."""

    def __init__(
        self,
        repository: DocumentRepository,
        organization_id: UUID,
        user_id: UUID,
        *,
        is_admin: bool,
    ) -> None:
        self.repository = repository
        self.organization_id = organization_id
        self.user_id = user_id
        self.is_admin = is_admin

    async def search(
        self, query: str, *, scope: RetrievalScope, limit: int
    ) -> list[RetrievedChunk]:
        if not scope.document_ids or not scope.version_ids or limit < 1:
            return []
        rows = await self.repository.sparse_search_chunks(
            self.organization_id,
            self.user_id,
            is_admin=self.is_admin,
            document_ids=scope.document_ids,
            version_ids=scope.version_ids,
            query=query,
            limit=limit,
        )
        return [
            RetrievedChunk(
                document_id=str(chunk.document_id),
                text=chunk.content,
                score=score,
                page_number=chunk.page_number,
                chunk_id=str(chunk.id),
                document_title=title,
                section_title=chunk.section_title
                or chunk.chunk_metadata.get("section_title"),
                version_id=str(chunk.version_id),
                token_count=chunk.token_count,
            )
            for chunk, title, score in rows
        ]

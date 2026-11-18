"""PostgreSQL repository for document metadata, ACLs, and versions."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import literal_column

from app.models import (
    Department,
    DepartmentMember,
    Document,
    DocumentChunk,
    DocumentPermission,
    DocumentVersion,
    IngestionJob,
    User,
)
from app.repositories.base import SQLAlchemyRepository


class DocumentRepository(SQLAlchemyRepository):
    async def find_department(
        self, department_id: UUID, organization_id: UUID
    ) -> Department | None:
        return await self.one_or_none(
            select(Department).where(
                Department.id == department_id,
                Department.organization_id == organization_id,
                Department.deleted_at.is_(None),
            )
        )

    async def find_duplicate(self, organization_id: UUID, file_hash: str):
        return await self.one_or_none(
            select(Document.id).where(
                Document.organization_id == organization_id,
                Document.file_hash == file_hash,
                Document.deleted_at.is_(None),
            )
        )

    async def count_authorized(self, organization_id: UUID, access_filter) -> int:
        return int(
            await self.scalar(
                select(func.count(Document.id)).where(
                    Document.organization_id == organization_id,
                    Document.deleted_at.is_(None),
                    Document.status != "deleted",
                    access_filter,
                )
            )
            or 0
        )

    async def authorized_indexed_versions(
        self, organization_id: UUID, user_id: UUID, *, is_admin: bool
    ) -> list[tuple[UUID, UUID]]:
        rows = await self.rows(
            select(Document.id, Document.current_version_id).where(
                Document.organization_id == organization_id,
                Document.status == "indexed",
                Document.deleted_at.is_(None),
                Document.current_version_id.is_not(None),
                self.access_filter(organization_id, user_id, is_admin=is_admin),
            )
        )
        return [(document_id, version_id) for document_id, version_id in rows]

    async def sparse_search_chunks(
        self,
        organization_id: UUID,
        user_id: UUID,
        *,
        is_admin: bool,
        document_ids: tuple[str, ...],
        version_ids: tuple[str, ...],
        query: str,
        limit: int,
    ) -> list[tuple[DocumentChunk, str, float]]:
        vector = func.to_tsvector(literal_column("'simple'"), DocumentChunk.content)
        terms = func.plainto_tsquery(literal_column("'simple'"), query)
        rank = func.ts_rank_cd(vector, terms)
        rows = await self.rows(
            select(DocumentChunk, Document.title, rank.label("rank"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.organization_id == organization_id,
                Document.status == "indexed",
                Document.deleted_at.is_(None),
                Document.id.in_([UUID(value) for value in document_ids]),
                Document.current_version_id == DocumentChunk.version_id,
                DocumentChunk.version_id.in_([UUID(value) for value in version_ids]),
                vector.op("@@")(terms),
                self.access_filter(organization_id, user_id, is_admin=is_admin),
            )
            .order_by(rank.desc(), DocumentChunk.id)
            .limit(limit)
        )
        return [(chunk, title, float(score)) for chunk, title, score in rows]

    async def authorized_chunks_by_ids(
        self,
        organization_id: UUID,
        user_id: UUID,
        *,
        is_admin: bool,
        chunk_ids: list[UUID],
    ) -> list[tuple[DocumentChunk, str]]:
        if not chunk_ids:
            return []
        rows = await self.rows(
            select(DocumentChunk, Document.title)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.id.in_(chunk_ids),
                Document.organization_id == organization_id,
                Document.status == "indexed",
                Document.deleted_at.is_(None),
                Document.current_version_id == DocumentChunk.version_id,
                self.access_filter(organization_id, user_id, is_admin=is_admin),
            )
        )
        return [(chunk, title) for chunk, title in rows]

    async def recent_authorized(
        self, organization_id: UUID, access_filter, page: int, page_size: int
    ) -> list[Document]:
        return await self.all(
            select(Document)
            .where(
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
                Document.status.notin_(("deleted", "archived")),
                access_filter,
            )
            .order_by(Document.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

    def list_documents(
        self,
        organization_id: UUID,
        access_filter,
        *,
        status_filter: str | None,
        department_id: UUID | None,
        owner_user_id: UUID | None,
        document_type: str | None,
    ):
        statement = select(Document).where(
            Document.organization_id == organization_id,
            Document.deleted_at.is_(None),
            Document.status.notin_(("deleted", "archived")),
            access_filter,
        )
        if status_filter:
            statement = statement.where(Document.status == status_filter)
        if department_id:
            statement = statement.where(Document.department_id == department_id)
        if owner_user_id:
            statement = statement.where(Document.owner_user_id == owner_user_id)
        if document_type:
            statement = statement.where(Document.document_type == document_type)
        return statement

    async def persist_initial_upload(
        self, document: Document, version: DocumentVersion, job: IngestionJob
    ) -> None:
        await self.add(document)
        await self.flush()
        version.document_id = document.id
        job.document_id = document.id
        await self.add(version)
        await self.flush()
        document.current_version_id = version.id
        await self.add(job)
        await self.commit()

    async def persist_version(
        self,
        document: Document,
        version: DocumentVersion,
        job: IngestionJob,
    ) -> None:
        await self.add(version)
        await self.add(job)
        await self.flush()
        document.current_version_id = version.id
        await self.commit()

    async def mark_ingestion_started(
        self, document: Document, job: IngestionJob
    ) -> None:
        now = datetime.now(timezone.utc)
        document.status = "processing"
        job.status = "running"
        job.attempts += 1
        job.started_at = now
        job.completed_at = None
        job.error_message = None
        await self.commit()

    async def persist_indexed_chunks(
        self,
        document: Document,
        job: IngestionJob,
        chunks: list[DocumentChunk],
    ) -> None:
        await self.session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.version_id == document.current_version_id,
            )
        )
        await self.add_all(chunks)
        document.status = "indexed"
        job.status = "succeeded"
        job.error_message = None
        job.completed_at = datetime.now(timezone.utc)
        await self.commit()

    async def mark_ingestion_failed(
        self,
        document: Document | None,
        job: IngestionJob | None,
        error_message: str,
        *,
        terminal: bool,
    ) -> None:
        if document is not None:
            document.status = "failed"
        if job is not None:
            job.status = "dead_letter" if terminal else "failed"
            job.error_message = error_message[:4000]
            if terminal:
                job.completed_at = datetime.now(timezone.utc)
        await self.commit()

    async def list_permissions(
        self, document_id: UUID, organization_id: UUID
    ) -> list[DocumentPermission]:
        return await self.all(
            select(DocumentPermission).where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.organization_id == organization_id,
            )
        )

    async def find_acl_target(self, grant_type: str, target_id: UUID, org_id: UUID):
        model = Department if grant_type == "department" else User
        statement = select(model.id).where(
            model.id == target_id,
            model.organization_id == org_id,
            model.deleted_at.is_(None),
        )
        return await self.one_or_none(statement)

    async def replace_permissions(
        self,
        document_id: UUID,
        organization_id: UUID,
        records: list[DocumentPermission],
    ) -> None:
        await self.session.execute(
            DocumentPermission.__table__.delete().where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.organization_id == organization_id,
            )
        )
        await self.add_all(records)
        await self.commit()

    @staticmethod
    def access_filter(organization_id: UUID, user_id: UUID, *, is_admin: bool):
        department_ids = (
            select(DepartmentMember.department_id)
            .join(Department, Department.id == DepartmentMember.department_id)
            .where(
                DepartmentMember.user_id == user_id,
                Department.organization_id == organization_id,
                Department.deleted_at.is_(None),
            )
        )
        matching_acl = or_(
            DocumentPermission.user_id == user_id,
            DocumentPermission.department_id.in_(department_ids),
            DocumentPermission.grant_type == "organization",
        )
        denied = exists(
            select(DocumentPermission.id).where(
                DocumentPermission.document_id == Document.id,
                DocumentPermission.organization_id == organization_id,
                DocumentPermission.permission == "deny",
                matching_acl,
            )
        )
        if is_admin:
            return ~denied
        allowed = exists(
            select(DocumentPermission.id).where(
                DocumentPermission.document_id == Document.id,
                DocumentPermission.organization_id == organization_id,
                DocumentPermission.permission.in_(("read", "write", "admin")),
                matching_acl,
            )
        )
        return ((Document.owner_user_id == user_id) | allowed) & ~denied

    def authorized_document_query(
        self,
        document_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        *,
        is_admin: bool,
    ):
        return select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
            Document.deleted_at.is_(None),
            Document.status.notin_(("deleted", "archived")),
            self.access_filter(organization_id, user_id, is_admin=is_admin),
        )


def document_repository(session: AsyncSession) -> DocumentRepository:
    return DocumentRepository(session)

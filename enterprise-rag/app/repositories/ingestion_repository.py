"""PostgreSQL repository for ingestion job state and transitions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IngestionJob
from app.repositories.base import SQLAlchemyRepository


class IngestionRepository(SQLAlchemyRepository):
    async def find_in_organization(
        self, job_id: UUID, organization_id: UUID
    ) -> IngestionJob | None:
        return await self.one_or_none(
            select(IngestionJob).where(
                IngestionJob.id == job_id,
                IngestionJob.organization_id == organization_id,
            )
        )

    def for_document(self, document_id: UUID, organization_id: UUID):
        return select(IngestionJob).where(
            IngestionJob.document_id == document_id,
            IngestionJob.organization_id == organization_id,
        )


def ingestion_repository(session: AsyncSession) -> IngestionRepository:
    return IngestionRepository(session)

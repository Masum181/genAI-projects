"""PostgreSQL aggregates for tenant analytics and operations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, IngestionJob, UsageRecord
from app.repositories.base import SQLAlchemyRepository


class AnalyticsRepository(SQLAlchemyRepository):
    async def usage_summary(
        self, organization_id: UUID, start_at: datetime | None, end_at: datetime | None
    ) -> tuple:
        statement = select(
            func.count(UsageRecord.id),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
            func.coalesce(func.sum(UsageRecord.cost_usd), 0),
            func.coalesce(func.avg(UsageRecord.latency_ms), 0),
        ).where(UsageRecord.organization_id == organization_id)
        if start_at:
            statement = statement.where(UsageRecord.created_at >= start_at)
        if end_at:
            statement = statement.where(UsageRecord.created_at <= end_at)
        return (await self.session.execute(statement)).one()

    async def documents_by_status(self, organization_id: UUID) -> list:
        statement = (
            select(Document.status, func.count(Document.id))
            .where(
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .group_by(Document.status)
        )
        return await self.rows(statement)

    async def ingestion_by_status(self, organization_id: UUID) -> list:
        statement = (
            select(IngestionJob.status, func.count(IngestionJob.id))
            .where(IngestionJob.organization_id == organization_id)
            .group_by(IngestionJob.status)
        )
        return await self.rows(statement)


def analytics_repository(session: AsyncSession) -> AnalyticsRepository:
    return AnalyticsRepository(session)

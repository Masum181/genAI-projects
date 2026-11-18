"""PostgreSQL repository for audit events and related admin summaries."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Document, IngestionJob, Organization, UsageRecord
from app.repositories.base import SQLAlchemyRepository


class AuditRepository(SQLAlchemyRepository):
    async def organization_metrics(self, organization_id: UUID):
        organization = await self.get(Organization, organization_id)
        if organization is None:
            return None
        document_count = int(
            await self.scalar(
                select(func.count(Document.id)).where(
                    Document.organization_id == organization_id,
                    Document.deleted_at.is_(None),
                )
            )
            or 0
        )
        job_counts = await self.rows(
            select(IngestionJob.status, func.count(IngestionJob.id))
            .where(IngestionJob.organization_id == organization_id)
            .group_by(IngestionJob.status)
        )
        request_count, total_cost = (
            await self.session.execute(
                select(
                    func.count(UsageRecord.id),
                    func.coalesce(func.sum(UsageRecord.cost_usd), 0),
                ).where(UsageRecord.organization_id == organization_id)
            )
        ).one()
        audit_count = int(
            await self.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.organization_id == organization_id
                )
            )
            or 0
        )
        return {
            "organization_id": str(organization_id),
            "documents": document_count,
            "ingestion_jobs_by_status": {
                job_status: count for job_status, count in job_counts
            },
            "usage_records": request_count,
            "cost_usd": float(total_cost),
            "audit_events": audit_count,
        }


def audit_repository(session: AsyncSession) -> AuditRepository:
    return AuditRepository(session)

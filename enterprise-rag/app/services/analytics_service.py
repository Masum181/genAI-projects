"""Tenant-scoped usage and product analytics use cases."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import Principal
from app.repositories.analytics_repository import AnalyticsRepository


def _authorize_analytics(principal: Principal) -> None:
    if not (
        principal.is_admin
        or {"analytics:read_org", "analytics:read_department"} & principal.permissions
    ):
        raise HTTPException(status_code=403, detail="Analytics permission required")


async def usage_analytics(
    session: AsyncSession,
    principal: Principal,
    start_at: datetime | None,
    end_at: datetime | None,
) -> dict:
    _authorize_analytics(principal)
    if start_at and end_at and start_at > end_at:
        raise HTTPException(status_code=422, detail="start_at must be before end_at")
    total, input_tokens, output_tokens, cost, avg_latency = await AnalyticsRepository(
        session
    ).usage_summary(principal.organization_id, start_at, end_at)
    return {
        "request_count": total,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": float(cost),
        "average_latency_ms": float(avg_latency),
        "start_at": start_at.isoformat() if start_at else None,
        "end_at": end_at.isoformat() if end_at else None,
    }


async def document_analytics(session: AsyncSession, principal: Principal) -> dict:
    _authorize_analytics(principal)
    repository = AnalyticsRepository(session)
    documents = await repository.documents_by_status(principal.organization_id)
    jobs = await repository.ingestion_by_status(principal.organization_id)
    return {
        "documents_by_status": {status: count for status, count in documents},
        "ingestion_jobs_by_status": {status: count for status, count in jobs},
    }

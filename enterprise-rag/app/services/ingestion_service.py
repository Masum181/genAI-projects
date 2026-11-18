"""Ingestion orchestration across storage, workers, and persistence."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import Principal
from app.models import IngestionJob
from app.repositories.ingestion_repository import IngestionRepository
from app.services.common import paginate_statement, serialize_model
from app.services.document_service import get_authorized_document


async def get_ingestion_job(
    session: AsyncSession, principal: Principal, job_id: UUID
) -> dict:
    job = await IngestionRepository(session).find_in_organization(
        job_id, principal.organization_id
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    if job.document_id is not None:
        await get_authorized_document(session, job.document_id, principal)
    elif "document:manage_org" not in principal.permissions and not principal.is_admin:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return serialize_model(job)


async def list_document_ingestion_jobs(
    session: AsyncSession,
    principal: Principal,
    document_id: UUID,
    page: int,
    page_size: int,
) -> dict:
    await get_authorized_document(session, document_id, principal)
    repository = IngestionRepository(session)
    return await paginate_statement(
        session,
        repository.for_document(document_id, principal.organization_id),
        page=page,
        page_size=page_size,
        order_column=IngestionJob.created_at,
    )

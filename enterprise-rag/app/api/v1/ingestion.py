"""Tenant-scoped ingestion job status endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Principal, get_current_principal, get_db
from app.api.v1.common import response
from app.services import ingestion_service

router = APIRouter(tags=["ingestion"])


@router.get("/ingestion-jobs/{job_id}")
async def get_ingestion_job(
    job_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await ingestion_service.get_ingestion_job(db, principal, job_id)
    return response(request, data)


@router.get("/documents/{document_id}/ingestion-jobs")
async def list_document_ingestion_jobs(
    document_id: UUID,
    request: Request,
    page: int = 1,
    page_size: int = 25,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await ingestion_service.list_document_ingestion_jobs(
        db, principal, document_id, page, page_size
    )
    return response(request, data)

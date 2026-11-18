"""HTTP endpoints for administrator health and operational metrics."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    Principal,
    get_current_principal,
    get_db,
    get_qdrant_client,
)
from app.api.responses import success_response
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/health")
async def admin_health(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> dict:
    data = await admin_service.health(principal, qdrant, request.app.state.redis)
    return success_response(request, data)


@router.get("/metrics")
async def admin_metrics(
    request: Request,
    organization_id: UUID | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await admin_service.metrics(db, principal, organization_id)
    return success_response(request, data)

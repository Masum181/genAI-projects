"""Organization-scoped analytics endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Principal, get_current_principal, get_db
from app.api.responses import success_response
from app.services import analytics_service

router = APIRouter(prefix="/admin/analytics", tags=["analytics"])


@router.get("/usage")
async def usage_analytics(
    request: Request,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await analytics_service.usage_analytics(db, principal, start_at, end_at)
    return success_response(request, data)


@router.get("/documents")
async def document_analytics(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await analytics_service.document_analytics(db, principal)
    return success_response(request, data)

"""Organization lifecycle endpoints for API version 1."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Principal, get_current_principal, get_db
from app.api.v1.common import response
from app.schemas.requests import OrganizationCreate, OrganizationUpdate
from app.services import organization_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("")
async def list_organizations(
    request: Request,
    page: int = 1,
    page_size: int = 25,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List organizations for a platform administrator or the current tenant."""
    data = await organization_service.list_organizations(
        db,
        principal,
        page=page,
        page_size=page_size,
    )
    return response(request, data)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a tenant; only platform administrators may create organizations."""
    data = await organization_service.create_organization(db, principal, body)
    return response(request, data)


@router.get("/{organization_id}")
async def get_organization(
    organization_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await organization_service.get_organization(db, principal, organization_id)
    return response(request, data)


@router.patch("/{organization_id}")
async def update_organization(
    organization_id: UUID,
    body: OrganizationUpdate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await organization_service.update_organization(
        db, principal, organization_id, body
    )
    return response(request, data)

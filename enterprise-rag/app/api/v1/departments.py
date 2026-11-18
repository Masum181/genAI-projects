"""Department management endpoints for API version 1."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Principal, get_current_principal, get_db
from app.api.v1.common import response
from app.schemas.requests import DepartmentCreate, DepartmentUpdate
from app.services import department_service

router = APIRouter(tags=["departments"])


@router.get("/organizations/{organization_id}/departments")
async def list_departments(
    organization_id: UUID,
    request: Request,
    page: int = 1,
    page_size: int = 25,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await department_service.list_departments(
        db, principal, organization_id, page, page_size
    )
    return response(request, data)


@router.post(
    "/organizations/{organization_id}/departments",
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    organization_id: UUID,
    body: DepartmentCreate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await department_service.create_department(
        db, principal, organization_id, body
    )
    return response(request, data)


@router.patch("/organizations/{organization_id}/departments/{department_id}")
async def update_department(
    organization_id: UUID,
    department_id: UUID,
    body: DepartmentUpdate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await department_service.update_department(
        db, principal, organization_id, department_id, body
    )
    return response(request, data)


@router.delete("/organizations/{organization_id}/departments/{department_id}")
async def delete_department(
    organization_id: UUID,
    department_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await department_service.delete_department(
        db, principal, organization_id, department_id
    )
    return response(request, data)


@router.get("/organizations/{organization_id}/departments/{department_id}/members")
async def list_department_members(
    organization_id: UUID,
    department_id: UUID,
    request: Request,
    page: int = 1,
    page_size: int = 25,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await department_service.list_department_members(
        db, principal, organization_id, department_id, page, page_size
    )
    return response(request, data)

"""Organization user management endpoints for API version 1."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import Principal, get_current_principal, get_db
from app.api.v1.common import response, serialize_model
from app.schemas.requests import UserInvite, UserStatusUpdate
from app.services import user_service

router = APIRouter(tags=["users"])


@router.get("/users/me")
async def get_me(
    request: Request, principal: Principal = Depends(get_current_principal)
) -> dict:
    user = serialize_model(principal.user)
    user["organization_id"] = str(principal.organization_id)
    user["roles"] = sorted(principal.role_names)
    user["permissions"] = sorted(principal.permissions)
    return response(request, user)


@router.get("/organizations/{organization_id}/users")
async def list_users(
    organization_id: UUID,
    request: Request,
    page: int = 1,
    page_size: int = 25,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return response(
        request,
        await user_service.list_users(db, principal, organization_id, page, page_size),
    )


@router.post(
    "/organizations/{organization_id}/users/invite",
    status_code=status.HTTP_201_CREATED,
)
async def invite_user(
    organization_id: UUID,
    body: UserInvite,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await user_service.invite_user(db, principal, organization_id, body)
    return response(request, data)


@router.patch("/organizations/{organization_id}/users/{user_id}")
async def update_user_status(
    organization_id: UUID,
    user_id: UUID,
    body: UserStatusUpdate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await user_service.update_user_status(
        db, principal, user_id, organization_id, body.status
    )
    return response(request, data)


@router.delete("/organizations/{organization_id}/users/{user_id}")
async def delete_user(
    organization_id: UUID,
    user_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await user_service.delete_user(db, principal, user_id, organization_id)
    return response(request, data)

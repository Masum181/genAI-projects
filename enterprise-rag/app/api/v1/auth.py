"""HTTP endpoints for authentication and API key lifecycle."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    Principal,
    bearer_scheme,
    get_current_principal,
    get_db,
)
from app.api.responses import success_response
from app.schemas.requests import (
    AcceptInviteRequest,
    APIKeyCreate,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_first_organization(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await auth_service.register_first_organization(db, body)
    return success_response(request, data)


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await auth_service.login(db, body)
    return success_response(request, data)


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await auth_service.refresh(db, request.app.state.redis, body.refresh_token)
    return success_response(request, data)


@router.post("/accept-invite")
async def accept_invitation(
    body: AcceptInviteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await auth_service.accept_invitation(
        db, body.invitation_token, body.password
    )
    return success_response(request, data)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    body: LogoutRequest | None = Body(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    access_token = (
        credentials.credentials if credentials else request.cookies.get("access_token")
    )
    await auth_service.logout(
        db,
        request.app.state.redis,
        principal,
        access_token,
        body.refresh_token if body else None,
        request.headers.get("x-api-key"),
    )
    response.delete_cookie("access_token", httponly=True, samesite="strict")
    return success_response(request, {"message": "Logged out"})


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: APIKeyCreate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await auth_service.create_api_key(db, principal, body)
    return success_response(request, data)


@router.get("/api-keys")
async def list_api_keys(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await auth_service.list_api_keys(db, principal)
    return success_response(request, data)


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await auth_service.revoke_api_key(db, principal, key_id)
    return success_response(request, data)


@router.get("/me")
async def current_user(
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    data = {
        "id": str(principal.user.id),
        "email": principal.user.email,
        "full_name": principal.user.full_name,
        "organization_id": str(principal.organization_id),
        "roles": sorted(principal.role_names),
        "permissions": sorted(principal.permissions),
    }
    return success_response(request, data)

"""User and organization membership use cases."""

import hashlib
import secrets
from datetime import timezone, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.identity import Principal
from app.models import APIKey, DepartmentMember, Membership, User
from app.repositories.user_repository import UserRepository
from app.schemas.requests import UserInvite
from app.services.common import paginate_statement, serialize_model


def _ensure_same_tenant(principal: Principal, organization_id: UUID) -> None:
    if principal.organization_id != organization_id and not principal.is_super_admin:
        raise HTTPException(status_code=404, detail="Resource not found")


async def list_users(
    session: AsyncSession,
    principal: Principal,
    organization_id: UUID,
    page: int,
    page_size: int,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    if not (
        principal.is_admin
        or "user:manage_org" in principal.permissions
        or "organization:read_self" in principal.permissions
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    repository = UserRepository(session)
    return await paginate_statement(
        session,
        repository.list_in_organization(organization_id),
        page=page,
        page_size=page_size,
        order_column=User.created_at,
    )


async def invite_user(
    session: AsyncSession,
    principal: Principal,
    organization_id: UUID,
    body: UserInvite,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    if not (principal.is_admin or "user:invite" in principal.permissions):
        raise HTTPException(
            status_code=403, detail="User invitation permission required"
        )
    if body.role == "organization_admin" and not principal.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Only organization administrators can invite administrators",
        )
    repository = UserRepository(session)
    role = await repository.find_role(organization_id, body.role)
    if role is None:
        raise HTTPException(status_code=400, detail="Requested role is not configured")
    if body.department_id is not None:
        department = await repository.find_department(
            body.department_id, organization_id
        )
        if department is None:
            raise HTTPException(status_code=404, detail="Department not found")
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.app.refresh_token_expire_days
    )
    user = User(
        organization_id=organization_id,
        email=body.email.lower(),
        full_name=body.full_name,
        status="invited",
    )
    invitation_token = secrets.token_urlsafe(32)
    membership = Membership(
        organization_id=organization_id,
        user_id=user.id,
        role_id=role.id,
        status="active",
    )
    key = APIKey(
        organization_id=organization_id,
        user_id=user.id,
        name=f"invite:{user.id}",
        key_hash=hashlib.sha256(invitation_token.encode()).hexdigest(),
        scopes=["invite"],
        expires_at=expires_at,
    )
    department_member = (
        DepartmentMember(
            department_id=body.department_id,
            user_id=user.id,
            role="member",
        )
        if body.department_id
        else None
    )
    try:
        await repository.create_invitation(user, membership, key, department_member)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="User already exists in organization"
        ) from exc
    return {
        "user": serialize_model(user),
        "invitation_token": invitation_token,
        "expires_at": expires_at.isoformat(),
    }


async def update_user_status(
    session: AsyncSession,
    principal: Principal,
    user_id: UUID,
    organization_id: UUID,
    status: str,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    if not principal.is_admin:
        raise HTTPException(
            status_code=403, detail="Organization administrator required"
        )
    repository = UserRepository(session)
    user = await repository.find_in_organization(user_id, organization_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = status
    return serialize_model(await repository.save(user))


async def delete_user(
    session: AsyncSession,
    principal: Principal,
    user_id: UUID,
    organization_id: UUID,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    if not principal.is_admin:
        raise HTTPException(
            status_code=403, detail="Organization administrator required"
        )
    if user_id == principal.user.id:
        raise HTTPException(
            status_code=409, detail="You cannot delete your own account"
        )
    repository = UserRepository(session)
    user = await repository.find_in_organization(user_id, organization_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = "disabled"
    user.deleted_at = datetime.now(timezone.utc)
    await repository.save(user)
    return {"id": str(user.id), "deleted": True}

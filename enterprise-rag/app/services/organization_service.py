"""Organization lifecycle use cases and tenant policy coordination."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import Principal
from app.models import Organization
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.requests import OrganizationCreate, OrganizationUpdate
from app.services.common import paginate_statement, serialize_model


async def list_organizations(
    session: AsyncSession,
    principal: Principal,
    *,
    page: int,
    page_size: int,
) -> dict:
    repository = OrganizationRepository(session)
    tenant_id = None if principal.is_super_admin else principal.organization_id
    return await paginate_statement(
        session,
        repository.list_visible(tenant_id),
        page=page,
        page_size=page_size,
        order_column=Organization.created_at,
    )


async def create_organization(
    session: AsyncSession, principal: Principal, body: OrganizationCreate
) -> dict:
    if not principal.is_super_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    organization = Organization(name=body.name, slug=body.slug, settings=body.settings)
    try:
        organization = await OrganizationRepository(session).create(organization)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Organization slug already exists"
        ) from exc
    return serialize_model(organization)


async def get_organization(
    session: AsyncSession, principal: Principal, organization_id: UUID
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    organization = await OrganizationRepository(session).find_active_by_id(
        organization_id
    )
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return serialize_model(organization)


async def update_organization(
    session: AsyncSession,
    principal: Principal,
    organization_id: UUID,
    body: OrganizationUpdate,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    if not principal.is_admin:
        raise HTTPException(
            status_code=403, detail="Organization administrator required"
        )
    repository = OrganizationRepository(session)
    organization = await repository.find_active_by_id(organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(organization, key, value)
    organization = await repository.update(organization)
    return serialize_model(organization)


def _ensure_same_tenant(principal: Principal, organization_id: UUID) -> None:
    if principal.organization_id != organization_id and not principal.is_super_admin:
        raise HTTPException(status_code=404, detail="Resource not found")

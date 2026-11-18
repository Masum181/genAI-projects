"""Department lifecycle and membership use cases."""

from datetime import timezone, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import Principal
from app.models import Department
from app.repositories.department_repository import DepartmentRepository
from app.schemas.requests import DepartmentCreate, DepartmentUpdate
from app.services.common import paginate_statement, serialize_model


def _can_manage(principal: Principal) -> bool:
    return bool(principal.is_admin or "department:manage_org" in principal.permissions)


def _ensure_same_tenant(principal: Principal, organization_id: UUID) -> None:
    if principal.organization_id != organization_id and not principal.is_super_admin:
        raise HTTPException(status_code=404, detail="Resource not found")


async def list_departments(
    session: AsyncSession,
    principal: Principal,
    organization_id: UUID,
    page: int,
    page_size: int,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    repository = DepartmentRepository(session)
    return await paginate_statement(
        session,
        repository.list_in_organization(organization_id),
        page=page,
        page_size=page_size,
        order_column=Department.name,
        sort_order="asc",
    )


async def create_department(
    session: AsyncSession,
    principal: Principal,
    organization_id: UUID,
    body: DepartmentCreate,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    if not _can_manage(principal):
        raise HTTPException(
            status_code=403, detail="Department management permission required"
        )
    repository = DepartmentRepository(session)
    if (
        body.parent_department_id is not None
        and await repository.find_parent(body.parent_department_id, organization_id)
        is None
    ):
        raise HTTPException(status_code=404, detail="Parent department not found")
    department = Department(
        organization_id=organization_id,
        name=body.name,
        parent_department_id=body.parent_department_id,
    )
    try:
        department = await repository.create(department)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Department name already exists"
        ) from exc
    return serialize_model(department)


async def update_department(
    session: AsyncSession,
    principal: Principal,
    organization_id: UUID,
    department_id: UUID,
    body: DepartmentUpdate,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    if not _can_manage(principal):
        raise HTTPException(
            status_code=403, detail="Department management permission required"
        )
    repository = DepartmentRepository(session)
    department = await repository.find_in_organization(department_id, organization_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    changes = body.model_dump(exclude_unset=True)
    parent_id = changes.get("parent_department_id")
    if parent_id is not None:
        parent = await repository.find_parent(parent_id, organization_id)
        if parent is None or parent.id == department.id:
            raise HTTPException(status_code=400, detail="Invalid parent department")
    for key, value in changes.items():
        setattr(department, key, value)
    try:
        department = await repository.save(department)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Department name already exists"
        ) from exc
    return serialize_model(department)


async def delete_department(
    session: AsyncSession,
    principal: Principal,
    organization_id: UUID,
    department_id: UUID,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    if not _can_manage(principal):
        raise HTTPException(
            status_code=403, detail="Department management permission required"
        )
    repository = DepartmentRepository(session)
    department = await repository.find_in_organization(department_id, organization_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    department.deleted_at = datetime.now(timezone.utc)
    await repository.commit()
    return {"id": str(department_id), "deleted": True}


async def list_department_members(
    session: AsyncSession,
    principal: Principal,
    organization_id: UUID,
    department_id: UUID,
    page: int,
    page_size: int,
) -> dict:
    _ensure_same_tenant(principal, organization_id)
    repository = DepartmentRepository(session)
    if await repository.find_in_organization(department_id, organization_id) is None:
        raise HTTPException(status_code=404, detail="Department not found")
    from app.models import User

    return await paginate_statement(
        session,
        repository.list_members(department_id, organization_id),
        page=page,
        page_size=page_size,
        order_column=User.email,
        sort_order="asc",
    )

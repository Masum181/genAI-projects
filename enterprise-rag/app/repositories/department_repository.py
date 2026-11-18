"""PostgreSQL repository for tenant-scoped department records."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Department, DepartmentMember, User
from app.repositories.base import SQLAlchemyRepository


class DepartmentRepository(SQLAlchemyRepository):
    def list_in_organization(self, organization_id: UUID):
        return select(Department).where(
            Department.organization_id == organization_id,
            Department.deleted_at.is_(None),
        )

    async def find_in_organization(
        self, department_id: UUID, organization_id: UUID
    ) -> Department | None:
        return await self.one_or_none(
            select(Department).where(
                Department.id == department_id,
                Department.organization_id == organization_id,
                Department.deleted_at.is_(None),
            )
        )

    async def find_parent(
        self, department_id: UUID, organization_id: UUID
    ) -> Department | None:
        return await self.find_in_organization(department_id, organization_id)

    async def create(self, department: Department) -> Department:
        await self.add(department)
        try:
            await self.commit()
        except IntegrityError:
            await self.rollback()
            raise
        await self.refresh(department)
        return department

    async def save(self, department: Department) -> Department:
        try:
            await self.commit()
        except IntegrityError:
            await self.rollback()
            raise
        await self.refresh(department)
        return department

    def list_members(self, department_id: UUID, organization_id: UUID):
        return (
            select(User)
            .join(DepartmentMember, DepartmentMember.user_id == User.id)
            .where(
                DepartmentMember.department_id == department_id,
                User.organization_id == organization_id,
                User.deleted_at.is_(None),
            )
        )


def department_repository(session: AsyncSession) -> DepartmentRepository:
    return DepartmentRepository(session)

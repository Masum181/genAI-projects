"""PostgreSQL repository for organization records."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization
from app.repositories.base import SQLAlchemyRepository


class OrganizationRepository(SQLAlchemyRepository):
    async def find_active_by_id(self, organization_id: UUID) -> Organization | None:
        return await self.one_or_none(
            select(Organization).where(
                Organization.id == organization_id,
                Organization.deleted_at.is_(None),
            )
        )

    def list_visible(self, organization_id: UUID | None = None) -> Any:
        statement = select(Organization).where(Organization.deleted_at.is_(None))
        if organization_id is not None:
            statement = statement.where(Organization.id == organization_id)
        return statement

    async def create(self, organization: Organization) -> Organization:
        await self.add(organization)
        try:
            await self.commit()
        except IntegrityError:
            await self.rollback()
            raise
        await self.refresh(organization)
        return organization

    async def update(self, organization: Organization) -> Organization:
        await self.commit()
        await self.refresh(organization)
        return organization


def organization_repository(session: AsyncSession) -> OrganizationRepository:
    return OrganizationRepository(session)

"""PostgreSQL repository for users, memberships, and identity queries."""

from uuid import UUID

from sqlalchemy import select

from app.models import (
    APIKey,
    Department,
    DepartmentMember,
    Membership,
    Organization,
    Role,
    User,
)
from app.repositories.base import SQLAlchemyRepository


class UserRepository(SQLAlchemyRepository):
    def list_in_organization(self, organization_id: UUID):
        return select(User).where(
            User.organization_id == organization_id,
            User.deleted_at.is_(None),
        )

    async def find_role(self, organization_id: UUID, role_name: str) -> Role | None:
        return await self.one_or_none(
            select(Role).where(
                Role.organization_id == organization_id,
                Role.name == role_name,
            )
        )

    async def find_department(
        self, department_id: UUID, organization_id: UUID
    ) -> Department | None:
        return await self.one_or_none(
            select(Department).where(
                Department.id == department_id,
                Department.organization_id == organization_id,
                Department.deleted_at.is_(None),
            )
        )

    async def add_member(self, member: DepartmentMember) -> None:
        await self.add(member)

    async def create_invitation(
        self,
        user: User,
        membership: Membership,
        api_key: APIKey,
        department_member: DepartmentMember | None,
    ) -> User:
        await self.add(user)
        await self.flush()
        membership.user_id = user.id
        api_key.user_id = user.id
        await self.add(membership)
        await self.add(api_key)
        if department_member is not None:
            department_member.user_id = user.id
            await self.add(department_member)
        await self.commit()
        await self.refresh(user)
        return user

    async def find_in_organization(
        self, user_id: UUID, organization_id: UUID
    ) -> User | None:
        return await self.one_or_none(
            select(User).where(
                User.id == user_id,
                User.organization_id == organization_id,
                User.deleted_at.is_(None),
            )
        )

    async def save(self, user: User) -> User:
        await self.commit()
        await self.refresh(user)
        return user

    async def find_active_identity(self, email: str, organization_slug: str | None):
        statement = (
            select(User, Organization)
            .join(Organization, Organization.id == User.organization_id)
            .where(
                User.email == email.lower(),
                User.status == "active",
                User.deleted_at.is_(None),
                Organization.status == "active",
                Organization.deleted_at.is_(None),
            )
        )
        if organization_slug:
            statement = statement.where(Organization.slug == organization_slug)
        return await self.rows(statement)

    async def has_active_membership(self, user_id: UUID, organization_id: UUID) -> bool:
        membership = await self.one_or_none(
            select(Membership.id).where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
                Membership.status == "active",
            )
        )
        return membership is not None

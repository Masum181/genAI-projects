"""Persistence queries used to resolve authenticated identities and permissions."""

import hashlib
from datetime import  datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    APIKey,
    Membership,
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.repositories.base import SQLAlchemyRepository


class AuthRepository(SQLAlchemyRepository):
    async def create_initial_organization(
        self, body, permissions_by_role: dict[str, list[str]], password_hash: str
    ) -> tuple[User, Organization]:
        from fastapi import HTTPException

        async with self.session.begin():
            await self.session.execute(text("SELECT pg_advisory_xact_lock(817230419)"))
            # organization_count = await self.session.scalar(
            #     select(func.count()).select_from(Organization)
            # )
            # if organization_count:
            #     raise HTTPException(
            #         status_code=403, detail="Initial registration is closed"
            #     )
            organization = Organization(
                name=body.organization_name,
                slug=body.organization_slug,
            )
            self.session.add(organization)
            await self.session.flush()
            roles = {}
            for role_name, permission_names in permissions_by_role.items():
                role = Role(
                    organization_id=organization.id,
                    name=role_name,
                    scope="organization",
                )
                self.session.add(role)
                await self.session.flush()
                roles[role_name] = role
                for permission_name in permission_names:
                    permission = await self.session.scalar(
                        select(Permission).where(Permission.name == permission_name)
                    )
                    if permission is None:
                        permission = Permission(
                            name=permission_name,
                            category=permission_name.split(":", maxsplit=1)[0],
                        )
                        self.session.add(permission)
                        await self.session.flush()
                    self.session.add(
                        RolePermission(role_id=role.id, permission_id=permission.id)
                    )
            user = User(
                organization_id=organization.id,
                email=body.email.lower(),
                full_name=body.full_name,
                password_hash=password_hash,
                status="active",
            )
            self.session.add(user)
            await self.session.flush()
            self.session.add(
                Membership(
                    organization_id=organization.id,
                    user_id=user.id,
                    role_id=roles["organization_admin"].id,
                    status="active",
                )
            )
        await self.session.refresh(user)
        return user, organization

    async def find_login_candidates(self, email: str, organization_slug: str | None):
        statement = (
            select(User, Organization)
            .join(Organization, Organization.id == User.organization_id)
            .where(
                func.lower(User.email) == email.lower(),
                User.status == "active",
                User.deleted_at.is_(None),
                Organization.status == "active",
                Organization.deleted_at.is_(None),
            )
        )
        if organization_slug:
            statement = statement.where(Organization.slug == organization_slug)
        return await self.rows(statement)

    async def active_membership(self, user_id, organization_id) -> Membership | None:
        return await self.one_or_none(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
                Membership.status == "active",
            )
        )

    async def find_active_user(self, user_id, organization_id) -> User | None:
        return await self.one_or_none(
            select(User).where(
                User.id == user_id,
                User.organization_id == organization_id,
                User.status == "active",
                User.deleted_at.is_(None),
            )
        )

    async def find_invitation(self, key_hash: str) -> APIKey | None:
        

        return await self.one_or_none(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.scopes.contains(["invite"]),
                APIKey.revoked_at.is_(None),
                APIKey.expires_at > datetime.now(timezone.utc),
            )
        )

    async def activate_invited_user(self, invitation: APIKey, password_hash: str):
        user = await self.one_or_none(
            select(User).where(
                User.id == invitation.user_id,
                User.organization_id == invitation.organization_id,
                User.status == "invited",
            )
        )
        if user is not None:
            

            user.password_hash = password_hash
            user.status = "active"
            invitation.revoked_at = datetime.now(timezone.utc)
            await self.commit()
        return user

    async def api_key_by_hash(self, key_hash: str, user_id=None) -> APIKey | None:
        statement = select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.revoked_at.is_(None),
        )
        if user_id is not None:
            statement = statement.where(APIKey.user_id == user_id)
        return await self.one_or_none(statement)

    async def create_api_key(self, api_key: APIKey) -> APIKey:
        await self.add(api_key)
        await self.commit()
        await self.refresh(api_key)
        return api_key

    async def list_api_keys(self, organization_id, user_id=None) -> list[APIKey]:
        statement = select(APIKey).where(
            APIKey.organization_id == organization_id,
            APIKey.revoked_at.is_(None),
        )
        if user_id is not None:
            statement = statement.where(APIKey.user_id == user_id)
        return await self.all(statement.order_by(APIKey.created_at.desc()))

    async def find_api_key_by_id(self, key_id, organization_id) -> APIKey | None:
        return await self.one_or_none(
            select(APIKey).where(
                APIKey.id == key_id,
                APIKey.organization_id == organization_id,
            )
        )

    async def find_api_key(self, secret: str) -> APIKey | None:
        key_hash = hashlib.sha256(secret.encode()).hexdigest()
        return await self.one_or_none(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.revoked_at.is_(None),
                (APIKey.expires_at.is_(None) | (APIKey.expires_at > datetime.now(timezone.utc))),
            )
        )

    async def find_active_membership_context(self, user_id, organization_id):
        user = await self.one_or_none(
            select(User).where(
                User.id == user_id,
                User.organization_id == organization_id,
                User.status == "active",
                User.deleted_at.is_(None),
            )
        )
        organization = await self.one_or_none(
            select(Organization).where(
                Organization.id == organization_id,
                Organization.status == "active",
                Organization.deleted_at.is_(None),
            )
        )
        membership = await self.one_or_none(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
                Membership.status == "active",
            )
        )
        return user, organization, membership

    async def role_and_permissions(self, role_id):
        role = await self.get(Role, role_id)
        permission_names = await self.all(
            select(Permission.name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        return role, permission_names


def auth_repository(session: AsyncSession) -> AuthRepository:
    return AuthRepository(session)

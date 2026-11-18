"""Authenticated principal context shared by API and application services."""

from dataclasses import dataclass
from uuid import UUID

from app.models import User


@dataclass(frozen=True)
class Principal:
    user: User
    organization_id: UUID
    role_names: frozenset[str]
    permissions: frozenset[str]
    is_api_key: bool = False

    @property
    def is_admin(self) -> bool:
        return not self.is_api_key and bool(
            self.role_names & {"super_admin", "organization_admin"}
        )

    @property
    def is_super_admin(self) -> bool:
        return not self.is_api_key and "super_admin" in self.role_names

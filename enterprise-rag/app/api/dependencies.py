"""Shared FastAPI dependencies for identity, authorization, and integrations."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import Principal
from app.database.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    """Resolve and validate the user's active tenant membership on every request."""
    from app.services.auth_service import resolve_principal

    return await resolve_principal(request, credentials, db)


def require_permissions(*permissions: str):
    """Create an authorization dependency that fails closed."""

    async def dependency(
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        if principal.is_admin:
            return principal
        if not set(permissions).issubset(principal.permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return principal

    return dependency


def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    """Return the application-scoped Qdrant client."""
    client: AsyncQdrantClient = request.app.state.qdrant_client
    return client

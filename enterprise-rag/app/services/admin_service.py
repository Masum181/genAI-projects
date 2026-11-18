"""Administrative health and metrics use cases."""

import logging
from uuid import UUID

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import Principal
from app.database.session import check_database_connection
from app.integrations.qdrant import check_qdrant_connection
from app.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)


def _authorize_admin(principal: Principal) -> None:
    if not (principal.is_admin or "platform:read_all" in principal.permissions):
        raise HTTPException(status_code=403, detail="Administrator permission required")


async def health(principal: Principal, qdrant, redis) -> dict:
    _authorize_admin(principal)
    dependencies: dict[str, str] = {}
    try:
        await check_database_connection()
        dependencies["database"] = "ok"
    except Exception:
        logger.exception("Administrative health check could not reach PostgreSQL")
        dependencies["database"] = "unavailable"
    try:
        await check_qdrant_connection(qdrant)
        dependencies["qdrant"] = "ok"
    except Exception:
        logger.exception("Administrative health check could not reach Qdrant")
        dependencies["qdrant"] = "unavailable"
    try:
        await redis.ping()
        dependencies["redis"] = "ok"
    except RedisError:
        logger.exception("Administrative health check could not reach Redis")
        dependencies["redis"] = "unavailable"
    return {
        "status": (
            "ok"
            if all(value == "ok" for value in dependencies.values())
            else "degraded"
        ),
        "dependencies": dependencies,
    }


async def metrics(
    session: AsyncSession,
    principal: Principal,
    organization_id: UUID | None,
) -> dict:
    _authorize_admin(principal)
    if not principal.is_super_admin or organization_id is None:
        organization_id = principal.organization_id
    data = await AuditRepository(session).organization_metrics(organization_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return data

"""Authentication use cases and identity-to-tenant resolution."""

import hashlib
import secrets
from uuid import UUID

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings
from app.core.identity import Principal
from app.core.security import hash_password, verify_password
from app.models import APIKey, User
from app.repositories.auth_repository import AuthRepository
from app.schemas.requests import (
    APIKeyCreate,
    LoginRequest,
    RegisterRequest,
)

DEFAULT_ROLE_PERMISSIONS = {
    "organization_admin": [
        "organization:read_self",
        "organization:update_self",
        "user:invite",
        "user:manage_org",
        "department:manage_org",
        "department:read_self",
        "document:upload",
        "document:manage_org",
        "document:read_authorized",
        "document:search_authorized",
        "chat:ask",
        "chat:history_view",
        "feedback:create",
        "analytics:read_org",
        "audit:read_org",
    ],
    "department_manager": [
        "department:read_self",
        "department:update_self",
        "user:manage_department",
        "document:upload",
        "document:read_department",
        "document:manage_department",
        "document:read_authorized",
        "document:search_authorized",
        "chat:ask",
        "chat:history_view",
        "feedback:create",
        "analytics:read_department",
    ],
    "employee": [
        "document:read_authorized",
        "document:search_authorized",
        "chat:ask",
        "chat:history_view",
        "feedback:create",
    ],
}


def token_data(user: User, organization_id) -> dict[str, object]:
    return {
        "access_token": create_access_token(str(user.id), str(organization_id)),
        "refresh_token": create_refresh_token(str(user.id), str(organization_id)),
        "token_type": "bearer",
        "expires_in": settings.app.access_token_expire_minutes * 60,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "organization_id": str(organization_id),
        },
    }


async def authenticate_browser(
    session: AsyncSession, email: str, password: str, organization_slug: str
) -> tuple[User, object] | None:
    repository = AuthRepository(session)
    candidates = await repository.find_login_candidates(
        email, organization_slug or None
    )
    if len(candidates) != 1:
        return None
    user, organization = candidates[0]
    if not verify_password(password, user.password_hash):
        return None
    if not await repository.active_membership(user.id, organization.id):
        return None
    return user, organization


async def register_first_organization(
    session: AsyncSession, body: RegisterRequest
) -> dict:
    user, organization = await AuthRepository(session).create_initial_organization(
        body,
        DEFAULT_ROLE_PERMISSIONS,
        hash_password(body.password),
    )
    return token_data(user, organization.id)


async def login(session: AsyncSession, body: LoginRequest) -> dict:
    candidates = await AuthRepository(session).find_login_candidates(
        body.email, body.organization_slug
    )
    if len(candidates) != 1:
        raise HTTPException(
            status_code=401,
            detail="Invalid email, password, or organization",
        )
    user, organization = candidates[0]
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email, password, or organization",
        )
    if not await AuthRepository(session).active_membership(user.id, organization.id):
        raise HTTPException(status_code=401, detail="Active membership required")
    return token_data(user, organization.id)


async def refresh(session: AsyncSession, redis, refresh_token: str) -> dict:
    try:
        claims = decode_token(refresh_token, expected_type="refresh")
        user_id, organization_id = UUID(claims["sub"]), UUID(claims["org"])
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired refresh token"
        ) from exc
    try:
        if await redis.exists(f"revoked-token:{claims['jti']}"):
            raise HTTPException(
                status_code=401, detail="Refresh token has been revoked"
            )
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="Authentication service unavailable"
        ) from exc
    repository = AuthRepository(session)
    user = await repository.find_active_user(user_id, organization_id)
    if user is None or not await repository.active_membership(user_id, organization_id):
        raise HTTPException(status_code=401, detail="Active membership required")
    await revoke_token(redis, claims)
    return token_data(user, organization_id)


async def accept_invitation(
    session: AsyncSession, invitation_token: str, password: str
) -> dict:
    key_hash = hashlib.sha256(invitation_token.encode()).hexdigest()
    repository = AuthRepository(session)
    invitation = await repository.find_invitation(key_hash)
    if invitation is None:
        raise HTTPException(status_code=400, detail="Invitation is invalid or expired")
    user = await repository.activate_invited_user(invitation, hash_password(password))
    if user is None:
        raise HTTPException(status_code=400, detail="Invitation is no longer valid")
    return token_data(user, invitation.organization_id)


async def logout(
    session: AsyncSession,
    redis,
    principal: Principal,
    access_token: str | None,
    refresh_token: str | None,
    api_key_secret: str | None,
) -> None:
    repository = AuthRepository(session)
    if api_key_secret:
        key_hash = hashlib.sha256(api_key_secret.encode()).hexdigest()
        api_key = await repository.api_key_by_hash(key_hash, principal.user.id)
        if api_key is not None:
            from datetime import datetime
            try:
                from datetime import UTC
            except ImportError:  # pragma: no cover
                from datetime import timezone
                UTC = timezone.utc

            api_key.revoked_at = datetime.now(UTC)
            await repository.commit()
    if access_token:
        try:
            claims = decode_token(access_token, expected_type="access")
        except InvalidTokenError as exc:
            raise HTTPException(status_code=401, detail="Invalid access token") from exc
        await revoke_token(redis, claims)
    if refresh_token:
        try:
            claims = decode_token(refresh_token, expected_type="refresh")
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=401, detail="Invalid refresh token"
            ) from exc
        if claims["sub"] != str(principal.user.id) or claims["org"] != str(
            principal.organization_id
        ):
            raise HTTPException(
                status_code=403, detail="Refresh token does not match session"
            )
        await revoke_token(redis, claims)


async def revoke_token(redis, claims: dict) -> None:
    from datetime import datetime
    try:
        from datetime import UTC
    except ImportError:  # pragma: no cover
        from datetime import timezone
        UTC = timezone.utc

    try:
        ttl = max(1, claims["exp"] - int(datetime.now(UTC).timestamp()))
        await redis.setex(f"revoked-token:{claims['jti']}", ttl, "1")
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="Authentication service unavailable"
        ) from exc


async def revoke_browser_access_token(redis, token: str) -> bool:
    try:
        claims = decode_token(token, expected_type="access")
    except InvalidTokenError:
        return False
    await revoke_token(redis, claims)
    return True


async def create_api_key(
    session: AsyncSession, principal: Principal, body: APIKeyCreate
) -> dict:
    requested_scopes = set(body.scopes)
    if not requested_scopes or not requested_scopes.issubset(principal.permissions):
        raise HTTPException(
            status_code=403, detail="Requested API key scopes are not allowed"
        )
    from datetime import datetime
    try:
        from datetime import UTC
    except ImportError:  # pragma: no cover
        from datetime import timezone
        UTC = timezone.utc

    if body.expires_at is not None and (
        body.expires_at.tzinfo is None
        or body.expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(
            status_code=422,
            detail="API key expiry must be timezone-aware and in the future",
        )
    secret = secrets.token_urlsafe(32)
    key = APIKey(
        organization_id=principal.organization_id,
        user_id=principal.user.id,
        name=body.name,
        key_hash=hashlib.sha256(secret.encode()).hexdigest(),
        scopes=sorted(requested_scopes),
        expires_at=body.expires_at,
    )
    key = await AuthRepository(session).create_api_key(key)
    return {
        "id": str(key.id),
        "name": key.name,
        "scopes": key.scopes,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "api_key": secret,
    }


async def list_api_keys(session: AsyncSession, principal: Principal) -> list[dict]:
    keys = await AuthRepository(session).list_api_keys(
        principal.organization_id,
        None if principal.is_admin else principal.user.id,
    )
    return [
        {
            "id": str(key.id),
            "name": key.name,
            "scopes": key.scopes,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "created_at": key.created_at.isoformat(),
        }
        for key in keys
    ]


async def revoke_api_key(session: AsyncSession, principal: Principal, key_id) -> dict:
    repository = AuthRepository(session)
    key = await repository.find_api_key_by_id(key_id, principal.organization_id)
    if key is None or (key.user_id != principal.user.id and not principal.is_admin):
        raise HTTPException(status_code=404, detail="API key not found")
    from datetime import datetime
    try:
        from datetime import UTC
    except ImportError:  # pragma: no cover
        from datetime import timezone
        UTC = timezone.utc

    key.revoked_at = datetime.now(UTC)
    await repository.commit()
    return {"id": str(key_id), "revoked": True}


async def resolve_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    session: AsyncSession,
) -> Principal:
    api_key_secret = request.headers.get("x-api-key")
    repository = AuthRepository(session)
    api_key = None
    if api_key_secret:
        api_key = await repository.find_api_key(api_key_secret)
        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
            )
        user_id, organization_id = api_key.user_id, api_key.organization_id
        token = None
    else:
        token = (
            credentials.credentials
            if credentials
            else request.cookies.get("access_token")
        )
    if not token and api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if token:
        try:
            claims = decode_token(token, expected_type="access")
            user_id = UUID(claims["sub"])
            organization_id = UUID(claims["org"])
        except (InvalidTokenError, ValueError, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        try:
            if await request.app.state.redis.exists(f"revoked-token:{claims['jti']}"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Access token has been revoked",
                )
        except RedisError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is temporarily unavailable",
            ) from exc

    user, organization, membership = await repository.find_active_membership_context(
        user_id, organization_id
    )
    if user is None or organization is None or membership is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Active organization membership required",
        )
    role, permissions = await repository.role_and_permissions(membership.role_id)
    scopes = frozenset(api_key.scopes) if api_key is not None else None
    effective_permissions = frozenset(permissions)
    if scopes is not None:
        effective_permissions &= scopes
    return Principal(
        user=user,
        organization_id=organization_id,
        role_names=frozenset({role.name}) if role is not None else frozenset(),
        permissions=effective_permissions,
        is_api_key=api_key is not None,
    )

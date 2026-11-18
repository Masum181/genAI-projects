"""Small HS256 JWT implementation using only the Python standard library."""

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4

from app.core.config import settings


class InvalidTokenError(ValueError):
    """Raised when a token is malformed, expired, or has an invalid signature."""


def _encode_part(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode()


def create_token(
    user_id: str, organization_id: str, *, token_type: str, expires_in: int
) -> str:
    """Create a signed access or refresh token."""
    header = _encode_part({"alg": "HS256", "typ": "JWT"})
    payload = _encode_part(
        {
            "sub": user_id,
            "org": organization_id,
            "type": token_type,
            "iat": int(time.time()),
            "exp": int(time.time()) + expires_in,
            "jti": str(uuid4()),
        }
    )
    signing_input = f"{header}.{payload}".encode()
    signature = hmac.new(
        settings.app.secret_key.encode(), signing_input, hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{header}.{payload}.{encoded_signature}"


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    """Verify token signature, claims, and expiration."""
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}".encode()
        expected_signature = hmac.new(
            settings.app.secret_key.encode(), signing_input, hashlib.sha256
        ).digest()
        supplied_signature = base64.urlsafe_b64decode(
            signature_part + "=" * (-len(signature_part) % 4)
        )
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise InvalidTokenError("Invalid token signature")
        header = json.loads(
            base64.urlsafe_b64decode(header_part + "=" * (-len(header_part) % 4))
        )
        payload: dict[str, Any] = json.loads(
            base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4))
        )
        if header.get("alg") != "HS256":
            raise InvalidTokenError("Unsupported token algorithm")
        if payload.get("type") != expected_type:
            raise InvalidTokenError("Unexpected token type")
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= time.time():
            raise InvalidTokenError("Token has expired")
        if not payload.get("sub") or not payload.get("org"):
            raise InvalidTokenError("Required token claims are missing")
        return payload
    except InvalidTokenError:
        raise
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise InvalidTokenError("Malformed token") from exc


def create_access_token(user_id: str, organization_id: str) -> str:
    """Create a short-lived access token."""
    return create_token(
        user_id,
        organization_id,
        token_type="access",
        expires_in=settings.app.access_token_expire_minutes * 60,
    )


def create_refresh_token(user_id: str, organization_id: str) -> str:
    """Create a refresh token with a longer lifetime."""
    return create_token(
        user_id,
        organization_id,
        token_type="refresh",
        expires_in=settings.app.refresh_token_expire_days * 86400,
    )

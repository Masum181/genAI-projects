"""Authentication token verification tests."""

import pytest

from app.auth.token import InvalidTokenError, create_access_token, decode_token
from app.core.config import settings


def test_access_token_contains_expected_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.app, "secret_key", "test-secret")

    claims = decode_token(
        create_access_token("user-id", "organization-id"),
        expected_type="access",
    )

    assert claims["sub"] == "user-id"
    assert claims["org"] == "organization-id"
    assert claims["type"] == "access"
    assert claims["jti"]


def test_access_token_rejects_tampering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.app, "secret_key", "test-secret")
    token = create_access_token("user-id", "organization-id")
    header, payload, signature = token.split(".")
    tampered_token = (
        f"{header}.{payload[:-1]}{('A' if payload[-1] != 'A' else 'B')}.{signature}"
    )

    with pytest.raises(InvalidTokenError):
        decode_token(tampered_token, expected_type="access")


def test_access_token_rejects_wrong_token_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.app, "secret_key", "test-secret")
    token = create_access_token("user-id", "organization-id")

    with pytest.raises(InvalidTokenError, match="Unexpected token type"):
        decode_token(token, expected_type="refresh")

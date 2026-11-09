"""Tests for environment-backed application settings."""

from app.core.config import Settings


def test_settings_have_local_development_defaults() -> None:
    """Settings defaults should be usable for local development."""
    settings = Settings()

    assert settings.app.api_v1_prefix == "/api/v1"
    assert settings.database.url.startswith("postgresql+asyncpg://")
    assert settings.qdrant.collection_name

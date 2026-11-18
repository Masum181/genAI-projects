"""Smoke test for the FastAPI liveness endpoint."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def connected_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep health endpoint tests independent from external services."""
    monkeypatch.setattr(main, "check_database_connection", AsyncMock())
    monkeypatch.setattr(main, "ensure_collection", AsyncMock())
    qdrant_client = Mock()
    qdrant_client.close = AsyncMock()
    monkeypatch.setattr(main, "create_qdrant_client", Mock(return_value=qdrant_client))


def test_health_endpoint_reports_liveness(connected_services: None) -> None:
    """The health endpoint responds without requiring external services."""
    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_checks_database_and_qdrant(
    connected_services: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Readiness is reported only when both data services are available."""
    monkeypatch.setattr(main, "check_qdrant_connection", AsyncMock())

    with TestClient(main.app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"database": "ok", "qdrant": "ok"},
    }


def test_readiness_endpoint_reports_database_failure(
    connected_services: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed dependency check returns an explicit non-ready response."""
    monkeypatch.setattr(
        main,
        "check_database_connection",
        AsyncMock(side_effect=[None, ConnectionError("database unavailable")]),
    )
    monkeypatch.setattr(main, "check_qdrant_connection", AsyncMock())

    with TestClient(main.app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {"database": "unavailable", "qdrant": "ok"},
    }

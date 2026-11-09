"""Smoke test for the FastAPI liveness endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_reports_liveness() -> None:
    """The health endpoint responds without requiring external services."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

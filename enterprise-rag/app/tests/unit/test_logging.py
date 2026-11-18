import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter, redact
from app.middleware.request_id import RequestIDMiddleware


def test_sensitive_values_are_redacted() -> None:
    value = {
        "password": "hunter2",
        "authorization": "Bearer secret",
        "api_key": "key",
        "question": "safe",
    }

    assert redact(value) == {
        "password": "[REDACTED]",
        "authorization": "[REDACTED]",
        "api_key": "[REDACTED]",
        "question": "safe",
    }


def test_json_formatter_emits_structured_output() -> None:
    record = logging.LogRecord(
        "app.test",
        logging.INFO,
        __file__,
        1,
        "operation succeeded",
        (),
        None,
    )
    record.operation = "test.operation"
    record.duration_ms = 12

    payload = json.loads(JsonFormatter().format(record))

    assert payload["logger"] == "app.test"
    assert payload["level"] == "INFO"
    assert payload["message"] == "operation succeeded"
    assert payload["operation"] == "test.operation"
    assert payload["duration_ms"] == 12


def test_request_id_is_generated_and_returned() -> None:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/test")

    assert response.headers["x-request-id"]
    assert response.headers["x-correlation-id"]
    assert response.status_code == 200


def test_valid_request_id_is_preserved() -> None:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get(
            "/test",
            headers={
                "X-Request-ID": "req-123",
                "X-Correlation-ID": "corr-456",
            },
        )

    assert response.headers["x-request-id"] == "req-123"
    assert response.headers["x-correlation-id"] == "corr-456"


@pytest.mark.parametrize("console", [False, True])
def test_logging_always_writes_file_and_optionally_echoes_to_terminal(
    tmp_path: Path, console: bool
) -> None:
    script = """
import logging
import sys
from pathlib import Path
from app.core.logging import configure_logging

configure_logging(
    console=sys.argv[2] == "true",
    log_dir=Path(sys.argv[1]),
    service_name="test",
)
logging.getLogger("test").info("persisted message")
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), str(console).lower()],
        capture_output=True,
        check=True,
        cwd=Path(__file__).resolve().parents[3],
        text=True,
    )

    log_file = tmp_path / "test.log"
    assert log_file.exists()
    assert "persisted message" in log_file.read_text(encoding="utf-8")
    assert ("persisted message" in result.stdout) is console

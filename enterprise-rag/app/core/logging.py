"""Central logging configuration and structured logging helpers."""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from datetime import UTC
except ImportError:  # pragma: no cover - Python < 3.11 compatibility
    from datetime import timezone

    UTC = timezone.utc
from typing import Any

from app.core.config import settings

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
task_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "task_id", default=None
)
log_service_name = settings.app.service_name

SENSITIVE_KEY = re.compile(
    r"(password|secret|token|authorization|cookie|api[_-]?key|credential)",
    re.IGNORECASE,
)


def redact(value: Any, *, depth: int = 0) -> Any:
    """Return a bounded, redacted representation of logging metadata."""
    if depth > 4:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if SENSITIVE_KEY.search(str(key))
            else redact(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return value[:2000]
    return value


class JsonFormatter(logging.Formatter):
    """Emit one Docker-friendly JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": log_service_name,
            "environment": settings.app.environment,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "correlation_id": correlation_id_var.get(),
            "task_id": task_id_var.get(),
        }
        reserved = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in reserved:
                payload[key] = redact(value)
        if record.exc_info:
            payload["stack_trace"] = self.formatException(record.exc_info)
            payload["exception_type"] = (
                record.exc_info[0].__name__ if record.exc_info[0] else None
            )
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(
    *,
    console: bool = False,
    log_dir: Path | None = None,
    service_name: str | None = None,
) -> None:
    """Write logs to a rotating file and optionally mirror them to the console."""
    global log_service_name

    level_name = getattr(settings.app, "log_level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    for existing_handler in root.handlers[:]:
        root.removeHandler(existing_handler)
        existing_handler.close()

    log_format = getattr(settings.app, "log_format", "json").lower()
    formatter = (
        JsonFormatter()
        if log_format == "json"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    directory = log_dir or Path(__file__).resolve().parents[2] / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    service = service_name or settings.app.service_name
    service = re.sub(r"[^A-Za-z0-9_.-]", "_", service) or "app"
    log_service_name = service
    file_handler = RotatingFileHandler(
        directory / f"{service}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)
    root.setLevel(level)


def set_request_context(
    request_id: str | None,
    correlation_id: str | None = None,
) -> tuple[contextvars.Token, contextvars.Token]:
    return (
        request_id_var.set(request_id),
        correlation_id_var.set(correlation_id or request_id),
    )


def set_task_context(task_id: str | None) -> contextvars.Token:
    return task_id_var.set(task_id)


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    operation: str | None = None,
    **fields: Any,
) -> None:
    """Log a single consistent event with optional structured fields."""
    event = {"operation": operation or message}
    event.update(redact(fields))
    logger.log(level, message, extra=event)

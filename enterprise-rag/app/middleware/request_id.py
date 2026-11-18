"""Request correlation identifier and HTTP lifecycle middleware."""

import logging
import re
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import (
    correlation_id_var,
    log_event,
    request_id_var,
    set_request_context,
)


class RequestIDMiddleware:
    """Attach a stable request ID to request state and response headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        supplied = headers.get(b"x-request-id", b"").decode("latin-1").strip()
        request_id = (
            supplied
            if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", supplied)
            else str(uuid4())
        )
        scope.setdefault("state", {})["request_id"] = request_id
        correlation = headers.get(b"x-correlation-id", b"").decode("latin-1").strip()
        correlation_id = (
            correlation
            if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", correlation)
            else request_id
        )
        scope["state"]["correlation_id"] = correlation_id
        request_token, correlation_token = set_request_context(
            request_id, correlation_id
        )
        started = time.perf_counter()
        status_code = 500
        logger = logging.getLogger("app.request")
        method = scope.get("method", "")
        path = scope.get("path", "")
        log_event(
            logger,
            logging.INFO,
            "HTTP request started",
            operation="http.request",
            method=method,
            path=path,
            request_id=request_id,
            correlation_id=correlation_id,
        )

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", request_id.encode("latin-1")))
                response_headers.append(
                    (b"x-correlation-id", correlation_id.encode("latin-1"))
                )
                message["headers"] = response_headers
                nonlocal status_code
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000)
            log_event(
                logger,
                logging.ERROR,
                "Unhandled HTTP request failure",
                operation="http.request",
                method=method,
                path=path,
                status=status_code,
                duration_ms=duration_ms,
                request_id=request_id,
                correlation_id=correlation_id,
            )
            logger.exception("Unhandled HTTP exception")
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000)
            log_event(
                logger,
                logging.INFO if status_code < 500 else logging.ERROR,
                "HTTP request completed",
                operation="http.request",
                method=method,
                path=path,
                status=status_code,
                duration_ms=duration_ms,
                request_id=request_id,
                correlation_id=correlation_id,
            )
            correlation_id_var.reset(correlation_token)
            request_id_var.reset(request_token)

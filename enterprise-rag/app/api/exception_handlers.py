"""Centralized translation of application exceptions into HTTP responses."""

import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import log_event

logger = logging.getLogger("app.exceptions")


def install_exception_handlers(app: FastAPI) -> None:
    """Register stable, request-correlated API error responses."""

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        _log_error(request, "NOT_FOUND", exc)
        return _error(request, 404, "NOT_FOUND", str(exc))

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        _log_error(request, "CONFLICT", exc)
        return _error(request, 409, "CONFLICT", str(exc))

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
        _log_error(request, "FORBIDDEN", exc)
        return _error(request, 403, "FORBIDDEN", str(exc))

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
        }.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        _log_error(request, code, exc)
        return _error(request, exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        _log_error(request, "VALIDATION_ERROR", exc)
        errors = [
            {"location": error["loc"], "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return _error(
            request,
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            details={"errors": errors},
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        _log_error(request, "INTERNAL_SERVER_ERROR", exc)
        logger.exception("Unhandled application exception")
        return _error(
            request,
            500,
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred",
        )


def _log_error(request: Request, code: str, exc: Exception) -> None:
    request_id = getattr(request.state, "request_id", None)
    low_severity = code in {
        "NOT_FOUND",
        "CONFLICT",
        "FORBIDDEN",
        "VALIDATION_ERROR",
    }
    log_event(
        logger,
        logging.WARNING if low_severity else logging.ERROR,
        "API exception handled",
        operation="api.exception",
        status=code,
        error_code=code,
        exception_type=type(exc).__name__,
        request_id=request_id,
    )


def _error(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    details: dict | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "success": False,
            "request_id": getattr(request.state, "request_id", str(uuid4())),
            "data": None,
            "error": {"code": code, "message": message, "details": details},
        },
    )

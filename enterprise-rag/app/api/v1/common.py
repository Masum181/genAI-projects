"""Common helpers for tenant-scoped API resources."""

from typing import Any

from fastapi import Request

from app.api.responses import success_response
from app.services.common import serialize_model as serialize_model


def response(request: Request, data: Any) -> dict[str, Any]:
    return success_response(request, data)

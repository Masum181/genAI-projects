"""Helpers for consistent API response envelopes."""

from typing import Any
from uuid import uuid4

from fastapi import Request


def success_response(request: Request, data: Any) -> dict[str, Any]:
    """Wrap endpoint data in the documented success envelope."""
    return {
        "success": True,
        "request_id": getattr(request.state, "request_id", str(uuid4())),
        "data": data,
        "error": None,
    }

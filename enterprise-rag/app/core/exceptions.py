"""Typed application exceptions shared across service and API boundaries."""


class NotFoundError(LookupError):
    """Requested resource does not exist in the authorized scope."""


class ConflictError(ValueError):
    """Requested operation conflicts with current resource state."""


class ForbiddenError(PermissionError):
    """The authenticated principal is not allowed to perform this operation."""

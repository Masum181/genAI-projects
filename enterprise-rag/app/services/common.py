"""Shared service-layer serialization and repository pagination."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import SQLAlchemyRepository


def serialize_model(model: Any) -> dict[str, Any]:
    """Serialize a mapped record without exposing password or key hashes."""
    excluded = {"password_hash", "key_hash"}
    result: dict[str, Any] = {}
    for column in model.__table__.columns:
        key = column.key
        if key in excluded:
            continue
        value = getattr(model, key)
        if isinstance(value, (UUID, datetime, date)):
            value = str(value)
        elif isinstance(value, Decimal):
            value = float(value)
        result[key] = value
    return result


async def paginate_statement(
    session: AsyncSession,
    statement: Any,
    *,
    page: int,
    page_size: int,
    order_column: Any,
    sort_order: str = "desc",
) -> dict[str, Any]:
    repository = SQLAlchemyRepository(session)
    try:
        records, total = await repository.paginate(
            statement,
            page=page,
            page_size=page_size,
            order_column=order_column,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Invalid pagination parameters"
        ) from exc
    return {
        "items": [serialize_model(record) for record in records],
        "page": page,
        "page_size": page_size,
        "total": total,
    }

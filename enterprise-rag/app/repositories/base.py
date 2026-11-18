"""Shared SQLAlchemy operations used by domain repositories."""

import logging
import time
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log_event

logger = logging.getLogger("app.database")

ModelT = TypeVar("ModelT")


class SQLAlchemyRepository:
    """Keep SQL execution and transaction control behind the repository layer."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, model: type[ModelT], entity_id: Any) -> ModelT | None:
        return await self.session.get(model, entity_id)

    async def one_or_none(self, statement: Any) -> Any:
        return await self.session.scalar(statement)

    async def all(self, statement: Any) -> list[Any]:
        return list((await self.session.scalars(statement)).all())

    async def rows(self, statement: Any) -> list[Any]:
        return list((await self.session.execute(statement)).all())

    async def scalar(self, statement: Any) -> Any:
        return await self.session.scalar(statement)

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        return instance

    async def add_all(self, instances: list[Any]) -> None:
        self.session.add_all(instances)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        started = time.perf_counter()
        try:
            await self.session.commit()
            log_event(
                logger,
                logging.DEBUG,
                "Database transaction committed",
                operation="database.commit",
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="succeeded",
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "Database transaction commit failed",
                operation="database.commit",
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_code="DATABASE_ERROR",
                exception_type=type(exc).__name__,
            )
            raise

    async def rollback(self) -> None:
        started = time.perf_counter()
        try:
            await self.session.rollback()
            log_event(
                logger,
                logging.WARNING,
                "Database transaction rolled back",
                operation="database.rollback",
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="succeeded",
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "Database rollback failed",
                operation="database.rollback",
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_code="DATABASE_ERROR",
                exception_type=type(exc).__name__,
            )
            raise

    async def refresh(self, instance: Any) -> None:
        await self.session.refresh(instance)

    async def paginate(
        self,
        statement: Any,
        *,
        page: int,
        page_size: int,
        order_column: Any,
        sort_order: str = "desc",
    ) -> tuple[list[Any], int]:
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("Invalid pagination parameters")
        total_statement = select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
        total = int(await self.session.scalar(total_statement) or 0)
        ordering = order_column.asc() if sort_order == "asc" else order_column.desc()
        records = (
            await self.session.scalars(
                statement.order_by(ordering)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return list(records), total

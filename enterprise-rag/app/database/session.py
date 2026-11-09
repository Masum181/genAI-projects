"""Async SQLAlchemy engine, session factory, and request dependency."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.database.url,
    echo=settings.database.echo,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session and always close it."""
    async with async_session_factory() as session:
        yield session

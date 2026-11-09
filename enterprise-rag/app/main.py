"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.database.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Release shared database resources when the application shuts down."""
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    debug=settings.app.debug,
    lifespan=lifespan,
)
app.include_router(api_v1_router, prefix=settings.app.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Return process liveness without claiming dependency readiness."""
    return {"status": "ok"}

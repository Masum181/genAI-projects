"""FastAPI application entry point."""

import argparse
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.api.exception_handlers import install_exception_handlers
from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.database.session import check_database_connection, engine
from app.integrations.llm.factory import close_llm_generator
from app.integrations.qdrant import (
    check_qdrant_connection,
    create_qdrant_client,
    ensure_collection,
)
from app.middleware.request_id import RequestIDMiddleware
from app.web import router as browser_router

logger = logging.getLogger(__name__)
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Connect to shared data services and release their resources on shutdown."""
    qdrant_client = create_qdrant_client()
    app.state.qdrant_client = qdrant_client
    redis_client = Redis.from_url(settings.redis.url, decode_responses=True)
    app.state.redis = redis_client
    try:
        await check_database_connection()
        await ensure_collection(qdrant_client)
        yield
    finally:
        await close_llm_generator()
        await redis_client.close()
        await qdrant_client.close()
        await engine.dispose()


app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    debug=settings.app.debug,
    lifespan=lifespan,
)
app.include_router(api_v1_router, prefix=settings.app.api_v1_prefix)
app.include_router(browser_router)
app.add_middleware(RequestIDMiddleware)
install_exception_handlers(app)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Return process liveness without claiming dependency readiness."""
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
async def readiness_check(request: Request) -> JSONResponse:
    """Report readiness only when PostgreSQL and Qdrant are available."""
    dependencies: dict[str, str] = {}

    try:
        await check_database_connection()
        dependencies["database"] = "ok"
    except Exception:
        logger.exception("PostgreSQL readiness check failed")
        dependencies["database"] = "unavailable"

    try:
        await check_qdrant_connection(request.app.state.qdrant_client)
        dependencies["qdrant"] = "ok"
    except Exception:
        logger.exception("Qdrant readiness check failed")
        dependencies["qdrant"] = "unavailable"

    status = (
        "ready"
        if all(value == "ok" for value in dependencies.values())
        else "not_ready"
    )
    status_code = 200 if status == "ready" else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "dependencies": dependencies},
    )


def main() -> None:
    """Run the API, optionally mirroring application logs to the terminal."""
    parser = argparse.ArgumentParser(description="Run the Enterprise RAG API")
    parser.add_argument(
        "--log",
        choices=("true", "false"),
        type=str.lower,
        default="false",
        help="also print application logs in the terminal (default: false)",
    )
    args = parser.parse_args()

    configure_logging(console=args.log == "true")
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)


if __name__ == "__main__":
    main()

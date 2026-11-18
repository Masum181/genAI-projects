"""MinIO object storage adapter."""

import logging
import time
from urllib.parse import urlsplit

from minio import Minio
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.logging import log_event

logger = logging.getLogger("app.storage")


class MinioStorage:
    """Async wrapper around the synchronous MinIO SDK."""

    def __init__(self) -> None:
        endpoint = urlsplit(settings.storage.endpoint_url)
        if not endpoint.hostname:
            raise ValueError("STORAGE_ENDPOINT_URL must contain a hostname")

        self.client = Minio(
            endpoint.netloc,
            access_key=settings.storage.ACCESS_KEY,
            secret_key=settings.storage.SECRET_KEY,
            secure=settings.storage.secure or endpoint.scheme == "https",
            region=settings.storage.region,
        )
        self.bucket = settings.storage.bucket

    async def upload(
        self, object_key: str, content: bytes, *, content_type: str
    ) -> None:
        started = time.perf_counter()
        try:
            await run_in_threadpool(self._upload, object_key, content, content_type)
            log_event(
                logger,
                logging.INFO,
                "Object storage upload completed",
                operation="storage.upload",
                object_key=object_key,
                content_type=content_type,
                size_bytes=len(content),
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="succeeded",
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "Object storage upload failed",
                operation="storage.upload",
                object_key=object_key,
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_code="STORAGE_ERROR",
                exception_type=type(exc).__name__,
            )
            raise

    def _upload(self, object_key: str, content: bytes, content_type: str) -> None:
        from io import BytesIO

        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket, location=settings.storage.region)
        self.client.put_object(
            self.bucket,
            object_key,
            BytesIO(content),
            length=len(content),
            content_type=content_type,
        )

    async def download(self, object_key: str) -> bytes:
        started = time.perf_counter()
        try:
            content = await run_in_threadpool(self._download, object_key)
            log_event(
                logger,
                logging.INFO,
                "Object storage download completed",
                operation="storage.download",
                object_key=object_key,
                size_bytes=len(content),
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="succeeded",
            )
            return content
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "Object storage download failed",
                operation="storage.download",
                object_key=object_key,
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_code="STORAGE_ERROR",
                exception_type=type(exc).__name__,
            )
            raise

    def _download(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def delete(self, object_key: str) -> None:
        await run_in_threadpool(self.client.remove_object, self.bucket, object_key)

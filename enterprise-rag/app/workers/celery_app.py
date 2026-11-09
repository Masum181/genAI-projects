"""Celery application configured with Redis as broker and result backend."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "enterprise_rag",
    broker=settings.redis.url,
    backend=settings.redis.url,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)

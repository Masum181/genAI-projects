"""Celery application configured with Redis as broker and result backend."""

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun

from app.core.config import settings
from app.core.logging import configure_logging, set_task_context

configure_logging(service_name="worker")

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
    worker_hijack_root_logger=False,
    imports=("app.workers.ingestion_worker",),
)


@task_prerun.connect
def _task_prerun(task_id=None, task=None, **kwargs):
    set_task_context(task_id)
    if task:
        import logging

        from app.core.logging import log_event

        log_event(
            logging.getLogger("app.task"),
            logging.INFO,
            "Celery task started",
            operation="task.started",
            task_id=task_id,
            task_name=getattr(task, "name", None),
        )


@task_postrun.connect
def _task_postrun(task_id=None, task=None, state=None, **kwargs):
    if task:
        import logging

        from app.core.logging import log_event

        log_event(
            logging.getLogger("app.task"),
            logging.INFO,
            "Celery task completed",
            operation="task.completed",
            task_id=task_id,
            task_name=getattr(task, "name", None),
            status=state,
        )


@task_failure.connect
def _task_failure(task_id=None, task=None, exception=None, traceback=None, **kwargs):
    import logging

    from app.core.logging import log_event

    log_event(
        logging.getLogger("app.task"),
        logging.ERROR,
        "Celery task failed",
        operation="task.failed",
        task_id=task_id,
        task_name=getattr(task, "name", None),
        status="failed",
        exception_type=type(exception).__name__ if exception else None,
        error_code="TASK_EXECUTION_ERROR",
    )

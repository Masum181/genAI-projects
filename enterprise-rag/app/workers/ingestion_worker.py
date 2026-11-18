"""Celery worker for extracting, embedding, and indexing uploaded documents."""

import asyncio
import logging
import random
from collections.abc import Coroutine
from typing import Any, TypeVar
from uuid import UUID

from qdrant_client import models

from app.core.logging import log_event
from app.database.session import async_session_factory, engine
from app.integrations.qdrant import create_qdrant_client, ensure_collection
from app.integrations.qdrant.collections import DOCUMENT_CHUNKS_COLLECTION
from app.integrations.storage.minio_storage import MinioStorage
from app.models import Document, DocumentChunk, DocumentVersion, IngestionJob
from app.rag.ingestion import IndexedChunk, index_document
from app.repositories.document_repository import DocumentRepository
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
MAX_RETRIES = 4
ResultT = TypeVar("ResultT")


@celery_app.task(
    bind=True,
    name="app.workers.ingestion_worker.ingest_document",
    max_retries=MAX_RETRIES,
)
def ingest_document(
    task,
    document_id: str,
    version_id: str,
    job_id: str,
) -> None:
    """Run document ingestion and retry transient failures with jitter."""
    identifiers = (UUID(document_id), UUID(version_id), UUID(job_id))
    log_event(
        logger,
        logging.INFO,
        "Document ingestion task received",
        operation="document.ingestion",
        task_id=task.request.id,
        document_id=document_id,
        retry_count=task.request.retries,
    )
    try:
        asyncio.run(_run_with_disposed_engine(_process_document(*identifiers)))
    except Exception as exc:
        terminal = task.request.retries >= MAX_RETRIES
        try:
            asyncio.run(
                _run_with_disposed_engine(
                    _record_failure(*identifiers, str(exc), terminal=terminal)
                )
            )
        except Exception:
            logger.exception(
                "Could not persist ingestion failure for document %s", document_id
            )
        if terminal:
            raise
        countdown = min(2**task.request.retries + random.uniform(0, 1), 300)
        raise task.retry(exc=exc, countdown=countdown, max_retries=MAX_RETRIES) from exc


async def _run_with_disposed_engine(
    operation: Coroutine[Any, Any, ResultT],
) -> ResultT:
    try:
        return await operation
    finally:
        await engine.dispose()


async def _process_document(
    document_id: UUID, version_id: UUID, job_id: UUID
) -> None:
    log_event(
        logger,
        logging.INFO,
        "Document ingestion processing started",
        operation="document.ingestion",
        stage="file_received",
        document_id=str(document_id),
    )
    async with async_session_factory() as session:
        repository = DocumentRepository(session)
        document = await repository.get(Document, document_id)
        version = await repository.get(DocumentVersion, version_id)
        job = await repository.get(IngestionJob, job_id)
        if document is None or version is None or job is None:
            raise ValueError("Ingestion document, version, or job no longer exists")
        if (
            version.document_id != document.id
            or job.document_id != document.id
            or job.organization_id != document.organization_id
        ):
            raise ValueError("Ingestion records do not belong to the same document")
        if job.status in {"succeeded", "dead_letter"}:
            return
        if document.current_version_id != version.id:
            raise ValueError("Document version was superseded before indexing")

        await repository.mark_ingestion_started(document, job)
        log_event(
            logger,
            logging.INFO,
            "Document ingestion file metadata loaded",
            operation="document.ingestion",
            stage="file_validation",
            document_id=str(document_id),
        )
        file_content = await MinioStorage().download(version.storage_key)
        log_event(
            logger,
            logging.INFO,
            "Document file downloaded from object storage",
            operation="document.ingestion",
            stage="file_uploaded",
            document_id=str(document_id),
        )
        qdrant = create_qdrant_client()
        indexing_started = False
        try:
            await ensure_collection(qdrant)
            indexing_started = True
            chunks = await index_document(
                qdrant,
                content=file_content,
                filename=version.storage_key.rsplit("/", maxsplit=1)[-1],
                source_title=document.title,
                content_hash=version.checksum,
                organization_id=document.organization_id,
                document_id=document.id,
                version_id=version.id,
                department_id=document.department_id,
            )
            await _remove_other_version_vectors(qdrant, document, version.id)
            await repository.persist_indexed_chunks(
                document, job, _to_document_chunks(document, version, chunks)
            )
        except Exception:
            if indexing_started:
                try:
                    await _remove_version_vectors(
                        qdrant, document.organization_id, document.id, version.id
                    )
                except Exception:
                    logger.exception(
                        "Could not remove partial vectors for document %s",
                        document.id,
                    )
            raise
        finally:
            await qdrant.close()


def _to_document_chunks(
    document: Document,
    version: DocumentVersion,
    chunks: list[IndexedChunk],
) -> list[DocumentChunk]:
    records = []
    for chunk in chunks:
        metadata: dict[str, str | int | bool] = {
            key: value for key, value in chunk.metadata.items() if key != "text"
        }
        records.append(
            DocumentChunk(
                id=chunk.point_id,
                document_id=document.id,
                version_id=version.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                token_count=chunk.token_count,
                chunk_metadata=metadata,
            )
        )
    return records


async def _remove_version_vectors(
    qdrant,
    organization_id: UUID,
    document_id: UUID,
    version_id: UUID,
) -> None:
    await qdrant.delete(
        collection_name=DOCUMENT_CHUNKS_COLLECTION,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="organization_id",
                        match=models.MatchValue(value=str(organization_id)),
                    ),
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=str(document_id)),
                    ),
                    models.FieldCondition(
                        key="document_version_id",
                        match=models.MatchValue(value=str(version_id)),
                    ),
                ]
            )
        ),
        wait=True,
    )


async def _remove_other_version_vectors(
    qdrant, document: Document, version_id: UUID
) -> None:
    await qdrant.delete(
        collection_name=DOCUMENT_CHUNKS_COLLECTION,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="organization_id",
                        match=models.MatchValue(value=str(document.organization_id)),
                    ),
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=str(document.id)),
                    ),
                ],
                must_not=[
                    models.FieldCondition(
                        key="document_version_id",
                        match=models.MatchValue(value=str(version_id)),
                    )
                ],
            )
        ),
        wait=True,
    )


async def _record_failure(
    document_id: UUID,
    version_id: UUID,
    job_id: UUID,
    error_message: str,
    *,
    terminal: bool,
) -> None:
    async with async_session_factory() as session:
        repository = DocumentRepository(session)
        document = await repository.get(Document, document_id)
        version = await repository.get(DocumentVersion, version_id)
        job = await repository.get(IngestionJob, job_id)
        if document is not None and (
            version is None or document.current_version_id != version.id
        ):
            document = None
        await repository.mark_ingestion_failed(
            document,
            job,
            error_message or "Document ingestion failed",
            terminal=terminal,
        )
        logger.error(
            "Document ingestion %s for %s",
            "exhausted retries" if terminal else "failed",
            document_id,
        )

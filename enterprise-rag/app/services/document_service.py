"""Document metadata, permission, and version lifecycle use cases."""

import hashlib
import logging
from datetime import timezone, datetime
from uuid import UUID

from fastapi import HTTPException
from minio.error import MinioException
from qdrant_client import models as qdrant_models
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import Principal
from app.integrations.qdrant.collections import DOCUMENT_CHUNKS_COLLECTION
from app.integrations.storage.minio_storage import MinioStorage
from app.models import (
    Document,
    DocumentPermission,
    DocumentVersion,
    IngestionJob,
)
from app.repositories.document_repository import DocumentRepository
from app.schemas.requests import DocumentMetadataUpdate, DocumentPermissionInput
from app.services.common import paginate_statement, serialize_model
from app.utils.file_validation import validate_upload

logger = logging.getLogger(__name__)


def document_access_filter(principal: Principal):
    return DocumentRepository.access_filter(
        principal.organization_id,
        principal.user.id,
        is_admin=principal.is_admin,
    )


async def get_authorized_document(
    session: AsyncSession, document_id: UUID, principal: Principal
) -> Document:
    repository = DocumentRepository(session)
    document = await repository.one_or_none(
        repository.authorized_document_query(
            document_id,
            principal.organization_id,
            principal.user.id,
            is_admin=principal.is_admin,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def _can_manage(principal: Principal) -> bool:
    return bool(
        principal.is_admin
        or {"document:manage_org", "document:manage_department"} & principal.permissions
    )


async def _enqueue_ingestion(
    session: AsyncSession,
    document: Document,
    version: DocumentVersion,
    job: IngestionJob,
) -> str:
    from app.workers.ingestion_worker import ingest_document

    try:
        task = ingest_document.delay(
            str(document.id),
            str(version.id),
            str(job.id),
        )
    except Exception as exc:
        logger.exception("Could not enqueue document ingestion for %s", document.id)
        await DocumentRepository(session).mark_ingestion_failed(
            document,
            job,
            "The ingestion task could not be queued",
            terminal=False,
        )
        raise HTTPException(
            status_code=503, detail="Document ingestion queue is unavailable"
        ) from exc
    return task.id


async def list_documents(
    session: AsyncSession,
    principal: Principal,
    *,
    page: int,
    page_size: int,
    status_filter: str | None,
    department_id: UUID | None,
    owner_user_id: UUID | None,
    document_type: str | None,
) -> dict:
    repository = DocumentRepository(session)
    statement = repository.list_documents(
        principal.organization_id,
        document_access_filter(principal),
        status_filter=status_filter,
        department_id=department_id,
        owner_user_id=owner_user_id,
        document_type=document_type,
    )
    from app.models import Document

    return await paginate_statement(
        session,
        statement,
        page=page,
        page_size=page_size,
        order_column=Document.updated_at,
    )


async def dashboard_document_count(session: AsyncSession, principal: Principal) -> int:
    repository = DocumentRepository(session)
    return await repository.count_authorized(
        principal.organization_id, document_access_filter(principal)
    )


async def list_browser_documents(
    session: AsyncSession,
    principal: Principal,
    page: int,
    page_size: int,
) -> list[Document]:
    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(status_code=422, detail="Invalid pagination parameters")
    return await DocumentRepository(session).recent_authorized(
        principal.organization_id,
        document_access_filter(principal),
        page,
        page_size,
    )


async def upload_document(
    session: AsyncSession,
    principal: Principal,
    file,
    *,
    title: str,
    document_type: str | None,
    department_id: UUID | None,
) -> dict:
    if not (principal.is_admin or "document:upload" in principal.permissions):
        raise HTTPException(
            status_code=403, detail="Document upload permission required"
        )
    repository = DocumentRepository(session)
    if (
        department_id
        and await repository.find_department(department_id, principal.organization_id)
        is None
    ):
        raise HTTPException(status_code=404, detail="Department not found")
    filename, content = await validate_upload(file)
    digest = hashlib.sha256(content).hexdigest()
    duplicate_id = await repository.find_duplicate(principal.organization_id, digest)
    if duplicate_id is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate document content; existing document is {duplicate_id}",
        )
    normalized_type = document_type or filename.rsplit(".", maxsplit=1)[-1].lower()
    mime_type = file.content_type or "application/octet-stream"
    document = Document(
        organization_id=principal.organization_id,
        department_id=department_id,
        owner_user_id=principal.user.id,
        title=title,
        storage_key="pending",
        mime_type=mime_type,
        file_hash=digest,
        document_type=normalized_type,
        status="uploaded",
    )
    await repository.add(document)
    await repository.flush()
    storage_key = f"{principal.organization_id}/{document.id}/v1/{filename}"
    document.storage_key = storage_key
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        storage_key=storage_key,
        checksum=digest,
    )
    job = IngestionJob(
        organization_id=principal.organization_id,
        document_id=document.id,
        job_type="document.upload",
        status="queued",
    )
    storage = MinioStorage()
    try:
        await storage.upload(storage_key, content, content_type=mime_type)
    except MinioException as exc:
        await repository.rollback()
        logger.exception(
            "Document upload failed for tenant %s", principal.organization_id
        )
        raise HTTPException(
            status_code=503, detail="Document storage is unavailable"
        ) from exc
    try:
        await repository.persist_initial_upload(document, version, job)
    except SQLAlchemyError:
        await repository.rollback()
        try:
            await storage.delete(storage_key)
        except MinioException:
            logger.exception("Could not remove orphaned upload %s", storage_key)
        raise
    task_id = await _enqueue_ingestion(session, document, version, job)
    return {
        "document_id": str(document.id),
        "ingestion_job_id": str(job.id),
        "status": job.status,
        "task_id": task_id,
        "upload_url": None,
    }


async def upload_document_version(
    session: AsyncSession, principal: Principal, document_id: UUID, file
) -> dict:
    document = await get_authorized_document(session, document_id, principal)
    if not _can_manage(principal) and document.owner_user_id != principal.user.id:
        raise HTTPException(
            status_code=403, detail="Document management permission required"
        )
    filename, content = await validate_upload(file)
    digest = hashlib.sha256(content).hexdigest()
    next_version = document.version_number + 1
    storage_key = (
        f"{principal.organization_id}/{document.id}/v{next_version}/{filename}"
    )
    mime_type = file.content_type or document.mime_type
    version = DocumentVersion(
        document_id=document.id,
        version_number=next_version,
        storage_key=storage_key,
        checksum=digest,
    )
    job = IngestionJob(
        organization_id=principal.organization_id,
        document_id=document.id,
        job_type="document.replace",
        status="queued",
    )
    storage = MinioStorage()
    try:
        await storage.upload(storage_key, content, content_type=mime_type)
    except MinioException as exc:
        logger.exception("Document version upload failed for %s", document_id)
        raise HTTPException(
            status_code=503, detail="Document storage is unavailable"
        ) from exc
    document.file_hash = digest
    document.storage_key = storage_key
    document.mime_type = mime_type
    document.document_type = filename.rsplit(".", maxsplit=1)[-1].lower()
    document.version_number = next_version
    document.status = "uploaded"
    try:
        await DocumentRepository(session).persist_version(document, version, job)
    except SQLAlchemyError:
        await DocumentRepository(session).rollback()
        try:
            await storage.delete(storage_key)
        except MinioException:
            logger.exception("Could not remove orphaned version %s", storage_key)
        raise
    task_id = await _enqueue_ingestion(session, document, version, job)
    return {
        "document_id": str(document.id),
        "document_version_id": str(version.id),
        "ingestion_job_id": str(job.id),
        "task_id": task_id,
        "version_number": next_version,
        "status": job.status,
    }


async def get_document(
    session: AsyncSession, principal: Principal, document_id: UUID
) -> dict:
    return serialize_model(
        await get_authorized_document(session, document_id, principal)
    )


async def download_document(
    session: AsyncSession, principal: Principal, document_id: UUID
) -> tuple[bytes, str]:
    document = await get_authorized_document(session, document_id, principal)
    try:
        return await MinioStorage().download(document.storage_key), document.mime_type
    except MinioException as exc:
        logger.exception("Document download failed for %s", document_id)
        raise HTTPException(
            status_code=503, detail="Document storage is unavailable"
        ) from exc


async def update_document(
    session: AsyncSession,
    principal: Principal,
    document_id: UUID,
    body: DocumentMetadataUpdate,
) -> dict:
    document = await get_authorized_document(session, document_id, principal)
    if not _can_manage(principal) and document.owner_user_id != principal.user.id:
        raise HTTPException(
            status_code=403, detail="Document management permission required"
        )
    changes = body.model_dump(exclude_unset=True)
    repository = DocumentRepository(session)
    department_id = changes.get("department_id")
    if (
        department_id is not None
        and await repository.find_department(department_id, principal.organization_id)
        is None
    ):
        raise HTTPException(status_code=404, detail="Department not found")
    for key, value in changes.items():
        setattr(document, key, value)
    await repository.commit()
    await repository.refresh(document)
    return serialize_model(document)


async def delete_document(
    session: AsyncSession, principal: Principal, document_id: UUID, qdrant
) -> dict:
    document = await get_authorized_document(session, document_id, principal)
    if not _can_manage(principal):
        raise HTTPException(
            status_code=403, detail="Document management permission required"
        )
    document.deleted_at = datetime.now(timezone.utc)
    document.status = "deleted"
    await DocumentRepository(session).commit()
    try:
        await qdrant.delete(
            collection_name=DOCUMENT_CHUNKS_COLLECTION,
            points_selector=qdrant_models.FilterSelector(
                filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="organization_id",
                            match=qdrant_models.MatchValue(
                                value=str(principal.organization_id)
                            ),
                        ),
                        qdrant_models.FieldCondition(
                            key="document_id",
                            match=qdrant_models.MatchValue(value=str(document_id)),
                        ),
                    ]
                )
            ),
        )
    except Exception as exc:
        logger.exception("Qdrant cleanup failed for document %s", document_id)
        raise HTTPException(
            status_code=503,
            detail="Document was disabled, but vector cleanup is pending",
        ) from exc
    return {"id": str(document_id), "deleted": True}


async def list_document_permissions(
    session: AsyncSession, principal: Principal, document_id: UUID
) -> list[dict]:
    await get_authorized_document(session, document_id, principal)
    if not _can_manage(principal):
        raise HTTPException(status_code=403, detail="Document ACL management required")
    records = await DocumentRepository(session).list_permissions(
        document_id, principal.organization_id
    )
    return [serialize_model(record) for record in records]


async def replace_document_permissions(
    session: AsyncSession,
    principal: Principal,
    document_id: UUID,
    grants: list[DocumentPermissionInput],
) -> list[dict]:
    await get_authorized_document(session, document_id, principal)
    if not _can_manage(principal):
        raise HTTPException(status_code=403, detail="Document ACL management required")
    if len(grants) > 500:
        raise HTTPException(status_code=422, detail="Too many ACL entries")
    repository = DocumentRepository(session)
    records = []
    for grant in grants:
        if grant.grant_type == "department":
            target_id = grant.department_id
            if target_id is None or grant.user_id is not None:
                raise HTTPException(
                    status_code=422, detail="Department grant requires department_id"
                )
        elif grant.grant_type == "user":
            target_id = grant.user_id
            if target_id is None or grant.department_id is not None:
                raise HTTPException(
                    status_code=422, detail="User grant requires user_id"
                )
        else:
            target_id = None
        if (
            target_id is not None
            and await repository.find_acl_target(
                grant.grant_type, target_id, principal.organization_id
            )
            is None
        ):
            raise HTTPException(status_code=404, detail="ACL target not found")
        records.append(
            DocumentPermission(
                document_id=document_id,
                organization_id=principal.organization_id,
                department_id=grant.department_id,
                user_id=grant.user_id,
                permission=grant.permission,
                grant_type=grant.grant_type,
            )
        )
    try:
        await repository.replace_permissions(
            document_id, principal.organization_id, records
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=422, detail="Invalid ACL entries") from exc
    return [serialize_model(record) for record in records]

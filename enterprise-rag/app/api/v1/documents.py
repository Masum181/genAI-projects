"""HTTP endpoints for tenant- and ACL-scoped document workflows."""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Request,
    Response,
    UploadFile,
    status,
)
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    Principal,
    get_current_principal,
    get_db,
    get_qdrant_client,
)
from app.api.v1.common import response
from app.schemas.requests import DocumentMetadataUpdate, DocumentPermissionInput
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents(
    request: Request,
    page: int = 1,
    page_size: int = 25,
    status_filter: str | None = None,
    department_id: UUID | None = None,
    owner_user_id: UUID | None = None,
    document_type: str | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await document_service.list_documents(
        db,
        principal,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        department_id=department_id,
        owner_user_id=owner_user_id,
        document_type=document_type,
    )
    return response(request, data)


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(min_length=1, max_length=255),
    document_type: str | None = Form(default=None, max_length=64),
    department_id: UUID | None = Form(default=None),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Store the file and enqueue extraction, embedding, and Qdrant indexing."""
    data = await document_service.upload_document(
        db,
        principal,
        file,
        title=title,
        document_type=document_type,
        department_id=department_id,
    )
    return response(request, data)


@router.post("/{document_id}/versions", status_code=status.HTTP_202_ACCEPTED)
async def upload_document_version(
    document_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await document_service.upload_document_version(
        db, principal, document_id, file
    )
    return response(request, data)


@router.get("/{document_id}")
async def get_document(
    document_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await document_service.get_document(db, principal, document_id)
    return response(request, data)


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> Response:
    content, mime_type = await document_service.download_document(
        db, principal, document_id
    )
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document_id}"',
            "Content-Length": str(len(content)),
        },
    )


@router.patch("/{document_id}")
async def update_document(
    document_id: UUID,
    body: DocumentMetadataUpdate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await document_service.update_document(db, principal, document_id, body)
    return response(request, data)


@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> dict:
    data = await document_service.delete_document(db, principal, document_id, qdrant)
    return response(request, data)


@router.get("/{document_id}/permissions")
async def list_document_permissions(
    document_id: UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await document_service.list_document_permissions(db, principal, document_id)
    return response(request, data)


@router.put("/{document_id}/permissions")
async def replace_document_permissions(
    document_id: UUID,
    grants: list[DocumentPermissionInput],
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await document_service.replace_document_permissions(
        db, principal, document_id, grants
    )
    return response(request, data)

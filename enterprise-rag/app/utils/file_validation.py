"""Document upload validation utilities."""

import re
from pathlib import PurePath

from fastapi import HTTPException, UploadFile

from app.core.config import settings

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".html", ".htm"}


def sanitize_filename(filename: str) -> str:
    """Reduce a filename to a safe basename that cannot traverse storage paths."""
    basename = PurePath(filename.replace("\\", "/")).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._")
    if not cleaned or cleaned in {".", ".."}:
        raise HTTPException(status_code=422, detail="Invalid file name")
    return cleaned[:200]


async def validate_upload(file: UploadFile) -> tuple[str, bytes]:
    """Read and validate a supported upload within the configured size limit."""
    filename = sanitize_filename(file.filename or "")
    suffix = PurePath(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported document type")
    content = await file.read(settings.storage.max_upload_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(content) > settings.storage.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds size limit")
    return filename, content

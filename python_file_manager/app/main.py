import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal
from app.models import UploadedFile

from app.services.minio_service import (
    create_bucket,
    upload_to_minio
)

from app.services.vector_service import (
    create_collection,
    store_code_vectors,
    search_code
)


app = FastAPI(
    title="Python Code Storage API",
    version="1.0.0"
)


@app.on_event("startup")
def startup():

    Base.metadata.create_all(bind=engine)

    create_bucket()

    create_collection()


@app.post("/upload")
def upload_python_file(
    file: UploadFile = File(...)
):

    # Validate extension
    if not file.filename or not file.filename.endswith(".py"):
        raise HTTPException(
            status_code=400,
            detail="Only python files are allowed"
        )

    content = file.file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Empty file"
        )

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Maximum file size is 5 MB"
        )

    try:
        code = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be UTF-8 encoded"
        )

    file_id = uuid.uuid4()

    object_name = f"{file_id}/{file.filename}"

    db: Session = SessionLocal()

    try:

        # 1. Upload original file to MinIO
        upload_to_minio(
            file_content=content,
            object_name=object_name
        )

        # 2. Save metadata in PostgreSQL
        uploaded_file = UploadedFile(
            id=file_id,
            filename=file.filename,
            object_name=object_name,
            file_size=len(content),
            status="uploaded"
        )

        db.add(uploaded_file)
        db.commit()

        # 3. Generate embeddings and store in Qdrant
        chunk_count = store_code_vectors(
            file_id=str(file_id),
            filename=file.filename,
            code=code
        )

        # 4. Update processing status
        uploaded_file.status = "indexed"
        db.commit()

        return {
            "message": "File uploaded and indexed successfully",
            "file_id": str(file_id),
            "filename": file.filename,
            "file_size": len(content),
            "chunks_created": chunk_count,
            "minio_object": object_name,
            "status": uploaded_file.status
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"File processing failed: {str(e)}"
        )

    finally:
        db.close()


@app.get("/search")
def search_python_code(query: str, limit: int = 5):

    results = search_code(query, limit)

    return {
        "query": query,
        "results": [
            {
                "score": point.score,
                "file_id": point.payload["file_id"],
                "filename": point.payload["filename"],
                "content": point.payload["content"],
                "start_line": point.payload["start_line"],
                "end_line": point.payload["end_line"]
            }
            for point in results
        ]
    }
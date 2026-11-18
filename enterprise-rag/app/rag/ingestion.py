"""Document extraction, chunk embedding, and Qdrant indexing."""

import logging
import math
import time
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings
from app.core.logging import log_event
from app.integrations.qdrant.collections import DOCUMENT_CHUNKS_COLLECTION
from app.rag.chunkers.fixed_chunker import FixedSizeChunker
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.embeddings.providers import SentenceTransformerEmbeddingProvider
from app.rag.extractors import extract_document

logger = logging.getLogger("app.document")

EMBEDDING_BATCH_SIZE = 64
UPSERT_BATCH_SIZE = 64


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    """A chunk and its deterministic identity, metadata, and vector."""

    point_id: UUID
    content: str
    page_number: int
    chunk_index: int
    char_start: int
    char_end: int
    token_count: int
    metadata: dict[str, str | int | bool]
    vector: list[float]


async def index_document(
    qdrant: AsyncQdrantClient,
    *,
    content: bytes,
    filename: str,
    source_title: str,
    content_hash: str,
    organization_id: UUID,
    document_id: UUID,
    version_id: UUID,
    department_id: UUID | None,
    embedding_provider: EmbeddingProvider | None = None,
) -> list[IndexedChunk]:
    """Extract a file, embed its chunks, and wait for Qdrant to store them."""
    started = time.perf_counter()
    log_event(
        logger,
        logging.INFO,
        "Document text extraction started",
        operation="document.ingestion",
        stage="text_extraction",
        document_id=str(document_id),
    )
    pages = await extract_document(content, filename=filename)
    log_event(
        logger,
        logging.INFO,
        "Document text extraction completed",
        operation="document.ingestion",
        stage="text_extraction",
        document_id=str(document_id),
        duration_ms=round((time.perf_counter() - started) * 1000),
        status="succeeded",
    )
    chunks = FixedSizeChunker().chunk(pages)
    if not chunks:
        raise ValueError("No searchable text could be extracted from the document")

    provider = embedding_provider or SentenceTransformerEmbeddingProvider()
    vectors: list[list[float]] = []
    texts = [chunk.text for chunk in chunks]
    embedding_started = time.perf_counter()
    log_event(
        logger,
        logging.INFO,
        "Document chunk embedding started",
        operation="document.ingestion",
        stage="embedding_generation",
        document_id=str(document_id),
        chunk_count=len(texts),
    )
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        vectors.extend(
            await provider.embed_documents(texts[start : start + EMBEDDING_BATCH_SIZE])
        )
    log_event(
        logger,
        logging.INFO,
        "Document chunk embedding completed",
        operation="document.ingestion",
        stage="embedding_generation",
        document_id=str(document_id),
        chunk_count=len(vectors),
        duration_ms=round((time.perf_counter() - embedding_started) * 1000),
        status="succeeded",
    )
    if len(vectors) != len(chunks):
        raise ValueError(
            f"Embedding provider returned {len(vectors)} vectors for "
            f"{len(chunks)} chunks"
        )

    indexed_chunks: list[IndexedChunk] = []
    page_metadata = {page.page_number: page.metadata for page in pages}
    for chunk, vector in zip(chunks, vectors, strict=True):
        if len(vector) != settings.embedding.dimensions:
            raise ValueError(
                f"Embedding dimension {len(vector)} does not match configured "
                f"dimension {settings.embedding.dimensions}"
            )
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("Embedding provider returned a non-finite vector")

        point_id = uuid5(
            NAMESPACE_URL,
            f"{organization_id}:{document_id}:{version_id}:{chunk.chunk_index}",
        )
        metadata: dict[str, str | int | bool] = {
            "organization_id": str(organization_id),
            "document_id": str(document_id),
            "document_version_id": str(version_id),
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "source_title": source_title,
            "file_name": filename,
            "content_hash": content_hash,
            "is_deleted": False,
            "token_count": chunk.token_count,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "embedding_model_name": settings.embedding.model_name,
            "text": chunk.text,
        }
        section_title = page_metadata[chunk.page_number].get("section_title")
        if section_title:
            metadata["section_title"] = section_title
        if department_id is not None:
            metadata["department_id"] = str(department_id)

        indexed_chunks.append(
            IndexedChunk(
                point_id=point_id,
                content=chunk.text,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                token_count=chunk.token_count,
                metadata=metadata,
                vector=[float(value) for value in vector],
            )
        )

    for start in range(0, len(indexed_chunks), UPSERT_BATCH_SIZE):
        batch = indexed_chunks[start : start + UPSERT_BATCH_SIZE]
        await qdrant.upsert(
            collection_name=DOCUMENT_CHUNKS_COLLECTION,
            points=[
                models.PointStruct(
                    id=str(chunk.point_id),
                    vector=chunk.vector,
                    payload=chunk.metadata,
                )
                for chunk in batch
            ],
            wait=True,
        )
    return indexed_chunks

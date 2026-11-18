"""Qdrant client creation, collection initialization, and health checks."""

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings


def create_qdrant_client() -> AsyncQdrantClient:
    """Create an async Qdrant client using centralized connection settings."""
    return AsyncQdrantClient(
        url=settings.qdrant.url,
        api_key=settings.qdrant.api_key,
    )


async def ensure_collection(client: AsyncQdrantClient) -> None:
    """Create the configured collection and required payload indexes if needed."""
    collection_name = settings.qdrant.collection_name
    dimensions = settings.embedding.dimensions

    if dimensions < 1:
        raise ValueError("EMBEDDING_DIMENSIONS must be a positive integer")

    if not await client.collection_exists(collection_name):
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=dimensions,
                distance=models.Distance.COSINE,
            ),
        )
    else:
        collection = await client.get_collection(collection_name)
        vector_config = collection.config.params.vectors
        if not isinstance(vector_config, models.VectorParams):
            raise ValueError(
                f"Qdrant collection {collection_name!r} must use unnamed vectors"
            )
        if vector_config.size != dimensions:
            raise ValueError(
                f"Qdrant collection {collection_name!r} has vector size "
                f"{vector_config.size}; configured embeddings require {dimensions}"
            )

    collection = await client.get_collection(collection_name)
    existing_indexes = collection.payload_schema or {}
    payload_indexes = {
        "organization_id": models.PayloadSchemaType.KEYWORD,
        "document_id": models.PayloadSchemaType.KEYWORD,
        "department_id": models.PayloadSchemaType.KEYWORD,
        "document_version_id": models.PayloadSchemaType.KEYWORD,
        "is_deleted": models.PayloadSchemaType.BOOL,
    }

    for field_name, field_schema in payload_indexes.items():
        if field_name not in existing_indexes:
            await client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_schema,
            )


async def check_qdrant_connection(client: AsyncQdrantClient) -> None:
    """Verify Qdrant connectivity and access to the configured collection."""
    await client.get_collection(settings.qdrant.collection_name)

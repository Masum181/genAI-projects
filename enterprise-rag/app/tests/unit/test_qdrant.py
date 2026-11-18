"""Tests for Qdrant collection initialization."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from qdrant_client import models

from app.integrations.qdrant.client import ensure_collection


def test_ensure_collection_creates_collection_and_payload_indexes() -> None:
    asyncio.run(_assert_collection_created_with_payload_indexes())


async def _assert_collection_created_with_payload_indexes() -> None:
    client = AsyncMock()
    client.collection_exists.return_value = False
    client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=models.VectorParams(
                    size=384,
                    distance=models.Distance.COSINE,
                )
            )
        ),
        payload_schema={},
    )

    await ensure_collection(client)

    client.create_collection.assert_awaited_once()
    assert client.create_collection.await_args.kwargs["vectors_config"].size == 384
    assert client.create_payload_index.await_count == 5


def test_ensure_collection_rejects_mismatched_vector_dimensions() -> None:
    asyncio.run(_assert_mismatched_vector_dimensions_rejected())


async def _assert_mismatched_vector_dimensions_rejected() -> None:
    client = AsyncMock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=models.VectorParams(
                    size=128,
                    distance=models.Distance.COSINE,
                )
            )
        ),
        payload_schema={},
    )

    try:
        await ensure_collection(client)
    except ValueError as exc:
        assert "configured embeddings require 384" in str(exc)
    else:
        raise AssertionError("Mismatched vector dimensions were accepted")

    client.create_collection.assert_not_awaited()
    client.create_payload_index.assert_not_awaited()

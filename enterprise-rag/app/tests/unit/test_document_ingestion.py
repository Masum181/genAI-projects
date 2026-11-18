"""Tests for end-to-end chunk embedding and Qdrant payload creation."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.config import settings
from app.rag.ingestion import index_document


class FakeEmbeddingProvider:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [float(len(text))] + [0.1] * 383


def test_index_document_upserts_tenant_scoped_chunks_to_qdrant(monkeypatch) -> None:
    monkeypatch.setattr(settings.embedding, "dimensions", 384)
    asyncio.run(_assert_index_document_upserts_chunks())


async def _assert_index_document_upserts_chunks() -> None:
    qdrant = AsyncMock()
    organization_id = uuid4()
    document_id = uuid4()
    version_id = uuid4()

    chunks = await index_document(
        qdrant,
        content=("policy information " * 950).encode(),
        filename="policy.txt",
        source_title="Employee Policy",
        content_hash="content-sha256",
        organization_id=organization_id,
        document_id=document_id,
        version_id=version_id,
        department_id=None,
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert len(chunks) == 3
    qdrant.upsert.assert_awaited_once()
    upsert = qdrant.upsert.await_args.kwargs
    assert upsert["wait"] is True
    assert upsert["collection_name"]
    points = upsert["points"]
    assert len(points) == 3
    payload = points[0].payload
    assert payload["organization_id"] == str(organization_id)
    assert payload["document_id"] == str(document_id)
    assert payload["document_version_id"] == str(version_id)
    assert payload["source_title"] == "Employee Policy"
    assert payload["content_hash"] == "content-sha256"
    assert payload["text"]
    assert points[0].vector == [0.1] * 384
    assert chunks[0].char_end > chunks[0].char_start
    assert chunks[1].char_start < chunks[0].char_end


def test_index_document_rejects_mismatched_embedding_dimensions(monkeypatch) -> None:
    monkeypatch.setattr(settings.embedding, "dimensions", 384)
    asyncio.run(_assert_mismatched_embedding_dimensions_rejected())


async def _assert_mismatched_embedding_dimensions_rejected() -> None:
    qdrant = AsyncMock()
    provider = SimpleNamespace(
        embed_documents=AsyncMock(return_value=[[0.1, 0.2]]),
        embed_query=AsyncMock(),
    )
    try:
        await index_document(
            qdrant,
            content=b"document content",
            filename="policy.txt",
            source_title="Employee Policy",
            content_hash="content-sha256",
            organization_id=uuid4(),
            document_id=uuid4(),
            version_id=uuid4(),
            department_id=None,
            embedding_provider=provider,
        )
    except ValueError as exc:
        assert "does not match configured dimension" in str(exc)
    else:
        raise AssertionError("Mismatched embedding dimensions were accepted")

    qdrant.upsert.assert_not_awaited()

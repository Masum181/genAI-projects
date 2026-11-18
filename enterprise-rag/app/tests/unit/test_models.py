"""Tests for SQLAlchemy model registration and schema conventions."""

from app.models import Base
from app.models.mixins import uuid7


def test_all_documented_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "organizations",
        "users",
        "memberships",
        "departments",
        "department_members",
        "roles",
        "permissions",
        "role_permissions",
        "documents",
        "document_versions",
        "document_permissions",
        "document_chunks",
        "ingestion_jobs",
        "conversations",
        "messages",
        "citations",
        "feedback",
        "audit_logs",
        "usage_records",
        "api_keys",
        "model_configurations",
    }


def test_document_chunk_maps_reserved_metadata_column() -> None:
    columns = Base.metadata.tables["document_chunks"].columns

    assert "metadata" in columns


def test_model_identifiers_are_uuid7() -> None:
    identifier = uuid7()

    assert identifier.version == 7

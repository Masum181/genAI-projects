# 09. Vector Database Design

## 1. Purpose of Qdrant
Qdrant stores vector embeddings and lightweight payload metadata for document chunks. It is optimized for fast semantic search but not for system of record metadata. PostgreSQL remains the source of truth for permissions, documents, versions, and ownership.

## 2. Collection design
Create one collection per tenant or one shared collection with a strict `organization_id` filter. Recommended pattern for enterprise scale:
- separate collection per tenant for stronger isolation,
- or a shared global collection with strict metadata filtering and high cardinality indexes.

### Recommended collection properties
- vector size depends on embedding model, e.g., 768 or 1024.
- distance metric: cosine or dot product depending on embedding normalization.
- payload indexes: `organization_id`, `document_id`, `department_id`, `document_version_id`.

## 3. Dense vector design
- Vector dimension aligned to chosen embedding model.
- Use the same model version across a collection.
- Store both semantic embeddings and metadata-only payload fields.

## 4. Sparse vector strategy
- BM25 or lexical sparse vectors are stored in parallel or as an auxiliary index when supported.
- Sparse retrieval uses tenant and permission filters to keep queries surgical.

## 5. Payload schema
```json
{
  "organization_id": "uuid",
  "document_id": "uuid",
  "document_version_id": "uuid",
  "department_id": "uuid",
  "chunk_index": 12,
  "page_number": 3,
  "section_title": "Expense Policy",
  "source_title": "Finance Handbook",
  "content_hash": "sha256:...",
  "is_deleted": false,
  "created_at": "2026-11-08T00:00:00Z"
}
```

## 6. Tenant isolation
Strict metadata filtering is mandatory:
```python
filters = {
    "must": [
        {"key": "organization_id", "match": {"value": tenant_id}},
        {"key": "is_deleted", "match": {"value": False}}
    ]
}
```
This prevents unauthorized cross-tenant retrieval even when the user query is not normalized correctly.

## 7. Department and document filters
- Filter document sets by department when department-level access is authorized.
- Filter by document IDs for explicit ACL assignments.
- Exclude archived and soft-deleted documents.

## 8. Point ID strategy
Use deterministic IDs for idempotent upsert:
- `hash(organization_id + document_id + version_id + chunk_index)`
- or a UUID generated on ingestion and stored in PostgreSQL for traceability.

## 9. Upsert strategy
- Upsert on deterministic IDs to allow retries without duplicate chunk creation.
- On document replacement, create new version and upsert only active chunk IDs.
- Remove stale chunks from previous version after validation and version cutover.

## 10. Deletion and reindexing
- Document deletion marks the document as inactive and removes vector points.
- Version updates remove stale version IDs from Qdrant after archival/cleanup.
- Reindexing may be required when model or collection parameters change.

## 11. Collection versioning
Track models and collection schema versions.
- `embedding_model_name`
- `vector_dimensions`
- `embedding_version`
- `schema_version`
This is critical when a model changes or a collection needs reprocessing.

## 12. Backup and recovery
- Back up Qdrant collection metadata and vector indexes according to retention policy.
- Maintain reconciliation jobs with PostgreSQL metadata to confirm all active document chunks exist in vector storage.
- Recovery must maintain filtered retrieval correctness and ACL metadata consistency.

## 13. Consistency with PostgreSQL metadata
Qdrant is never the authoritative record for access control. PostgreSQL metadata controls:
- active/inactive status,
- version ownership,
- department and user ACLs,
- document-level access changes.
Qdrant payloads are used for efficient filtering and retrieval but do not replace the application policy model.

## 14. Related documents
- [05-database-design.md](./05-database-design.md)
- [08-rag-pipeline.md](./08-rag-pipeline.md)
- [12-background-processing.md](./12-background-processing.md)

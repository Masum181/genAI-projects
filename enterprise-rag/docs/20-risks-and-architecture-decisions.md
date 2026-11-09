# 20. Risk Register and Technical Decision Records

## 1. Risk register
| Risk | Category | Severity | Mitigation |
|---|---|---|---|
| Cross-tenant leakage | Security | Critical | Authorization before retrieval; RLS; Qdrant filters |
| Prompt injection in documents | Security | Critical | Evidence isolation; no direct instruction trust |
| Retrieval quality degradation | Performance/Quality | High | Hybrid search and reranking |
| LLM cost overrun | Cost | High | Budget alerts and model routing |
| Job processing failure | Reliability | High | Retry policies and DLQ |
| Document version drift | Data consistency | Medium | Active version logic and cleanup |

## 2. ADRs

### ADR-01: Modular monolith vs microservices
Context: Need fast delivery while keeping architecture extensible.
Decision: Use modular monolith initially with domain boundaries.
Consequences: Simpler deployment, easier governance, clearer path to decomposition later.

### ADR-02: PostgreSQL vs alternative databases
Decision: Use PostgreSQL for metadata and business data.
Reason: strong relational schema, transaction support, and safe permission modeling.

### ADR-03: Qdrant selection
Decision: Use Qdrant for vector indexing with metadata filters.
Advantages: explicit metadata filtering, efficient approximate search, and strong support for enterprise retrieval patterns.

### ADR-04: Dense vs hybrid retrieval
Decision: Use hybrid retrieval with dense + sparse + reranking.
Rationale: enterprise content often includes both nuanced semantics and exact terminology.

### ADR-05: Chunking strategy
Decision: Use structure-aware chunking with token targets and overlap.
Benefits: better evidence boundaries and fewer lost citations.

### ADR-06: Embedding model selection
Decision: Use BGE or equivalent sentence transformer model family with versioned metadata.
Use model versioning to support reindexing and drift management.

### ADR-07: Celery and Redis
Decision: Use Celery for async processing and Redis for broker plus cache.
This aligns with Python ecosystem and supports scalable ingestion.

### ADR-08: Cloud vs local LLM
Decision: support both, with abstraction layer and policy-based selection.
This enables secure local deployments while supporting cloud providers where needed.

### ADR-09: Object storage
Decision: MinIO or S3-compatible object storage with versioned keys and restricted tenant access.
This separates document data from metadata and supports recovery.

### ADR-10: Tenant isolation strategy
Decision: Use tenant-aware schema, backend validation, metadata filters, and RLS as defense-in-depth.
This is critical because enterprise RAG must preserve knowledge isolation.

## 3. Open questions
- Whether local LLM deployment is required for all regulated environments.
- Whether document approval workflows are mandatory or optional.
- Whether to support SSO only in later releases or from the start.

## 4. Related documents
- [19-implementation-roadmap.md](./19-implementation-roadmap.md)
- [10-security-and-privacy.md](./10-security-and-privacy.md)
- [08-rag-pipeline.md](./08-rag-pipeline.md)

# Architectural Review

**Audit date:** 2026-11-12  
**Scope:** Application layering, module boundaries, authorization placement, persistence, external integrations, background processing, and operability  
**Method:** Static review of `app/`, `alembic/`, deployment files, and tests

## 1. Architecture summary

The system is a modular monolith with these principal flows:

```text
Browser / API client
        |
        v
FastAPI routers (app/api/v1, app/web.py)
        |
        v
Services (authorization, use cases, orchestration)
        |
        v
Repositories (SQLAlchemy queries/transactions API)
        |
        +--> PostgreSQL
        +--> Qdrant (dense vectors)
        +--> MinIO (objects)
        +--> Redis (revocation, Celery broker/backend)
        +--> LLM providers (Ollama/OpenAI/Gemini)
```

Background ingestion:

```text
Upload -> MinIO -> Document/Version/Job rows -> Celery task
      -> extraction -> chunking -> embeddings -> Qdrant upsert
      -> DocumentChunk rows -> document indexed
```

Chat:

```text
Question -> Principal resolution -> authorized indexed versions
        -> dense (Qdrant) + sparse (PostgreSQL FTS) -> RRF
        -> cross-encoder rerank -> grounded prompt -> provider JSON
        -> citation validation -> messages/citations/usage persistence
```

The architecture is directionally sound for the documented modular monolith. The main problems are not the high-level boundaries; they are authorization consistency, transactional consistency across PostgreSQL/Qdrant/MinIO, and the absence of production operations.

## 2. Architectural strengths

### 2.1 Clear module boundaries

- API modules handle HTTP concerns; services own use cases; repositories own SQLAlchemy operations.
- `app/tests/unit/test_layering.py` enforces the API/session and service/repository direction via AST parsing.
- Integration adapters are isolated under `app/integrations/` and RAG components under `app/rag/`.
- Background work is isolated in `app/workers/`.

### 2.2 Server-resolved tenant identity

- The client does not supply authoritative `organization_id` for document/chat access; `Principal` is resolved from the token/API key and active membership.
- Document, conversation, feedback, ingestion, department, and organization queries generally include tenant filters.
- `DocumentRepository.access_filter` combines owner, user, department, and organization grants with explicit-deny precedence.

### 2.3 Retrieval authorization before search

- The retrieval service first resolves `authorized_indexed_versions` in PostgreSQL, then builds a Qdrant scope of allowed document/version IDs.
- Qdrant payload filters include organization ID, document IDs, version IDs, and `is_deleted=False`.
- Fused results are re-verified against PostgreSQL before reranking.

### 2.4 Prompt and output isolation

- Retrieved evidence is serialized as untrusted content, separate from system instructions.
- The prompt instructs the model to answer only from evidence and refuse when insufficient.
- Generated JSON is schema-validated; citation IDs must match supplied evidence before citations are persisted.
- Provider failures are converted to controlled 503 responses for generation.

### 2.5 Background-processing discipline

- Ingestion uses bounded retries with jitter and terminal dead-letter behavior.
- Version/job identity is checked before processing; superseded versions are rejected.
- Partial vectors are cleaned on indexing failure.
- The async engine is disposed after task execution.

### 2.6 Authentication foundations

- Custom HS256 JWT validates signature, type, expiration, and required claims.
- Refresh tokens are rotated and revoked through Redis.
- API-key scopes are intersected with role permissions.
- Password hashing uses PBKDF2-HMAC-SHA256 with 310,000 rounds and constant-time comparison.

## 3. Architectural weaknesses

### 3.1 Authorization is ad hoc and inconsistent

Authorization is implemented in individual services with different patterns:

- Some endpoints check permissions; others only resolve tenant membership.
- `require_permissions` exists in `app/api/dependencies.py:25` but is unused.
- `Principal.is_admin` bypasses all individual permission checks in that helper.
- Document management checks permission presence but not resource scope.
- Department/member listing has no permission check.
- Analytics accepts a department-scoped permission but queries organization-wide data.
- Unused permissions such as `department:update_self`, `document:read_department`, `audit:read_org`, and `user:manage_department` have no enforcement path.

**Consequence:** Authorization correctness depends on remembering the right ad hoc check in every new service method. The existing defects are predictable results of this pattern.

**Recommendation:** Centralize policy decisions in explicit policy objects/functions, e.g. `can_manage_document(principal, document)`, `can_read_department(principal, department_id)`, `can_view_analytics(principal, scope)`. Add deny-by-default tests for every route/service.

### 3.2 Tenant isolation relies only on application code

- No PostgreSQL RLS policies exist.
- Several tenant-adjacent queries join through parent tables rather than carrying `organization_id` directly (e.g., department membership), so correctness depends on join filters.
- `memberships.role_id` lacks a foreign key, so role integrity is not enforced by the database.
- The database schema is not created by migrations, so the intended constraints/indexes are not actually deployable.

**Recommendation:** Add RLS as defense in depth, restore the missing FK, and make migrations the only schema path.

### 3.3 Transaction boundaries are unclear and cross-store

Examples:

- `upload_document` writes DB rows, uploads to MinIO, and enqueues Celery; failure handling compensates manually.
- `delete_document` commits the DB soft delete before Qdrant cleanup; cleanup failure returns 503 but leaves orphaned vectors.
- Ingestion indexes new vectors, removes other-version vectors, then persists chunk rows; a DB failure can leave no vectors.
- Services call `repository.commit()` directly, so multi-step use cases cannot be composed atomically.
- Some repository methods commit internally while others do not.

**Consequence:** Partial failures create inconsistent PostgreSQL/Qdrant/MinIO state and make retries/idempotency difficult.

**Recommendation:** Introduce explicit unit-of-work/transaction boundaries in services, use an outbox or durable job state for cross-store cleanup, and make compensating actions idempotent.

### 3.4 No production operations layer

- No migrations or startup schema check.
- No rate limiting, audit writes, metrics, tracing, or alerting.
- No Nginx/TLS terminator; datastore ports are exposed.
- Redis and Qdrant are unauthenticated in Compose.
- No CI/pre-commit gate.
- No object-storage retention/secure-deletion workflow.

**Consequence:** The system cannot be operated safely or diagnosed under failure.

### 3.5 Retrieval and generation failure semantics are incomplete

- Only embedding and LLM provider errors are mapped to controlled responses.
- Qdrant, reranker, and PostgreSQL full-text failures can surface as unhandled 500s.
- There is no reranker confidence threshold or deterministic insufficient-evidence decision before generation.
- SSE is simulated after full generation, so the streaming architecture is not real.
- Usage accounting is heuristic.

**Recommendation:** Define a retrieval result contract with stage status, fallbacks, and confidence. Map each external failure to a documented response. Stream provider tokens if SSE is required.

### 3.6 Search design diverges from the documented vector model

- The documented design describes Qdrant sparse vectors/BM25 alongside dense vectors.
- Implementation uses PostgreSQL `to_tsvector`/`ts_rank_cd` through `SparseRetriever`, not Qdrant sparse vectors.
- This is defensible as a lexical fallback, but it changes operational characteristics and should be documented as an intentional decision.

### 3.7 Frontend and API are mismatched in scope

- Browser UI covers login, dashboard counts, document list, conversation list, and logout.
- Upload, chat, citations, feedback, ingestion status, ACL management, and admin screens are API-only.
- The current UI is explicitly documented as incomplete in `docs/16-frontend-ux-specification.md`.
- Root `/` currently crashes due to a cookie API typo.

### 3.8 Test architecture does not protect the architecture

- 24 tests, mostly unit/smoke.
- Empty integration, security, and evaluation directories.
- No tests for the layering rules under runtime conditions, authorization scope, ACL deny precedence, or tenant boundaries.
- Dependency declaration is broken (`httpx2`), so the documented test environment is not reproducible.

## 4. Authorization placement review

| Area | Current placement | Assessment |
|---|---|---|
| Authentication | `resolve_principal` in auth service | Good; validates tenant membership and key scope |
| Admin/platform | `admin_service._authorize_admin` | Reasonable, but `platform:read_all` role is not seeded |
| Documents | `document_service` ad hoc checks | Defective scope checks |
| Document ACL | `document_service` + repository target lookup | Target tenant checked; caller authority not scoped |
| Analytics | `analytics_service._authorize_analytics` | Permission/query mismatch |
| Departments | `department_service` + controller | Listing unprotected; management too org-centric |
| Conversations | `conversation_service` history permission | Good for history; verify all mutations |
| Ingestion | `ingestion_service` authorized-document check | Good |
| Feedback | `feedback_service` ownership | Good for reads; verify create target authorization |
| Organizations | `organization_service` | Super-admin path unreachable; get lacks explicit read permission |

## 5. Recommended target architecture changes

1. **Policy layer:** Create explicit authorization functions for every resource/action, including scope. Keep controllers thin.
2. **Unit of work:** Give services a transaction boundary; ensure repositories never commit independently.
3. **Outbox/cleanup jobs:** Persist intended Qdrant/MinIO operations, then execute idempotently in workers.
4. **Schema lifecycle:** Add migrations, startup version checks, and a migration deployment job.
5. **Security middleware:** Add rate limiting, security headers, CSRF protection for cookie sessions, and audit event emission.
6. **Observability:** Add request-scoped structured logs, OpenTelemetry spans, metrics, and RAG-stage traces.
7. **Evaluation harness:** Add offline retrieval/generation evaluation with CI thresholds.
8. **Super-admin provisioning:** Add a supported bootstrap/CLI path and tests for multi-tenant creation.
9. **Documentation alignment:** Update `03`, `06`, `08`, `09`, `15`, and `16` to match intended behavior, then enforce with tests.

## 6. Overall architectural verdict

**Partially compliant with the documented architecture.** The modular boundaries and RAG pipeline are credible foundations, but authorization placement, transaction design, deployment readiness, and operations are not yet at the level required by the SRS/security/deployment documents.

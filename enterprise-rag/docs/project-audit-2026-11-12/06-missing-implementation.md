# Missing Implementation

**Audit date:** 2026-11-12  
**Scope:** Documented capabilities that are absent, partial, or unreachable  
**Note:** This report distinguishes “no code” from “code exists but is not wired/enforced.” Items already detailed in `03-critical-issues.md` are summarized rather than repeated in full.

## 1. Security and governance

| Missing capability | Status | Evidence / notes | Required by |
|---|---|---|---|
| Initial schema/migration | `NOT_IMPLEMENTED` | No Alembic revisions; `init_db.py` stub | `05`, `15` |
| Secret validation / fail-closed config | `NOT_IMPLEMENTED` | Default JWT secret; no production validation | `10`, `15` |
| MFA for privileged roles | `NOT_IMPLEMENTED` | No MFA fields/flow | `02`, `10`, `16` |
| Rate limiting | `NOT_IMPLEMENTED` | No middleware/dependency | `10` |
| CSRF protection | `NOT_IMPLEMENTED` | Cookie auth present; no CSRF token mechanism | `10` |
| Malware scanning/quarantine | `NOT_IMPLEMENTED` | Extension/size validation only | `07`, `10` |
| Audit-log writes | `NOT_IMPLEMENTED` | Model/repository read only | `10` |
| PostgreSQL RLS | `NOT_IMPLEMENTED` | Application-only tenant filters | `10` |
| Security headers / CORS policy | `NOT_IMPLEMENTED` | Only request-ID middleware | `10` |
| Idempotency-key enforcement | `NOT_IMPLEMENTED` | No idempotency storage/replay | `06`, `12` |
| Data retention / secure deletion | `PARTIALLY_COMPLIANT` | Soft delete exists; no retention job; objects remain | `10`, `15` |
| Backup/restore/rollback automation | `NOT_IMPLEMENTED` | No scripts or CI jobs | `15` |

## 2. Identity, tenancy, and roles

| Missing capability | Status | Evidence / notes | Required by |
|---|---|---|---|
| Super-admin bootstrap | `NOT_IMPLEMENTED` | No role seeded; all super-admin paths unreachable | `03`, `17` |
| Second-organization provisioning | `NOT_IMPLEMENTED` | Initial registration is one-time; create requires super admin | `02`, `03` |
| Platform-wide role/permission management | `NOT_IMPLEMENTED` | No API for role CRUD or permission assignment | `03` |
| Department membership management | `NOT_IMPLEMENTED` | Only listing; invitation can set a department; no add/remove for existing users | `03`, `17` |
| Department-scoped manager authority | `PARTIALLY_COMPLIANT` | `_can_manage` requires org-level permission; scope checks absent | `03` |
| Organization suspension workflow | `PARTIALLY_COMPLIANT` | `OrganizationUpdate.status` exists; no dedicated workflow/audit/session invalidation | `10`, `17` |
| Session invalidation on suspension | `PARTIALLY_COMPLIANT` | Each request checks active org; issued tokens are not explicitly revoked | `10`, `17` |
| User deletion/retention workflow | `PARTIALLY_COMPLIANT` | Disables/soft-deletes user; no data retention/purge | `10` |
| Role FK integrity | `NOT_IMPLEMENTED` | `memberships.role_id` lacks FK | `05` |

## 3. Document lifecycle

| Missing capability | Status | Evidence / notes | Required by |
|---|---|---|---|
| Default department ACL on upload | `NOT_IMPLEMENTED` | `department_id` metadata only; no permission row | `03`, `07` |
| Department-scoped upload/manage | `PARTIALLY_COMPLIANT` | Permission exists; target department not verified | `03`, `06` |
| View/download endpoint scope | `PARTIALLY_COMPLIANT` | Authorized-document checks present; no write/download audit | `06`, `10` |
| Version replacement transactional cleanup | `PARTIALLY_COMPLIANT` | Indexing removes old vectors before DB chunk persistence | `07`, `12` |
| Object-storage purge on delete | `NOT_IMPLEMENTED` | Soft delete + vector delete only | `10`, `17` |
| Archived/replaced status workflow | `PARTIALLY_COMPLIANT` | Statuses exist; replacement does not clearly archive prior versions | `05`, `17` |
| Malware/quarantine workflow | `NOT_IMPLEMENTED` | No scan status/queue | `07`, `10` |
| Duplicate handling without ID disclosure | `NOT_IMPLEMENTED` | 409 includes existing document ID | `06` |
| Idempotent upload | `NOT_IMPLEMENTED` | No idempotency key | `06`, `12` |

## 4. Ingestion and background jobs

| Missing capability | Status | Evidence / notes | Required by |
|---|---|---|---|
| OCR fallback | `NOT_IMPLEMENTED` | No OCR path | `07` |
| Semantic/structure-aware chunking | `NOT_IMPLEMENTED` | Fixed 900-word/120-word chunking | `07`, `08` |
| Real token accounting | `NOT_IMPLEMENTED` | Word counts and character heuristics | `08`, `13` |
| Cleanup/reindex/metrics task types | `NOT_IMPLEMENTED` | Only `ingest_document` task | `12` |
| Dead-letter inspection/retry API | `PARTIALLY_COMPLIANT` | Status stored; no admin retry/list-by-dead-letter workflow | `12` |
| Worker queue monitoring | `NOT_IMPLEMENTED` | No queue-depth/saturation metrics | `14` |
| Re-embedding on model change | `NOT_IMPLEMENTED` | No migration/reindex task | `09` |
| Idempotent ingestion | `PARTIALLY_COMPLIANT` | Job/version checks present; no idempotency key | `12` |

## 5. Retrieval and generation

| Missing capability | Status | Evidence / notes | Required by |
|---|---|---|---|
| Query rewrite/expansion/routing | `NOT_IMPLEMENTED` | NFKC + whitespace only | `08` |
| Qdrant sparse vectors/BM25 | `NOT_IMPLEMENTED` | PostgreSQL FTS instead | `08`, `09` |
| Reranker confidence/refusal threshold | `NOT_IMPLEMENTED` | Top results always passed onward | `08` |
| Context compression | `NOT_IMPLEMENTED` | No compression/dedup | `08` |
| Retrieval failure fallback | `PARTIALLY_COMPLIANT` | Only embedding/LLM errors mapped | `08` |
| True token streaming | `NOT_IMPLEMENTED` | SSE slices completed answer | `06`, `08` |
| Provider-reported token usage | `NOT_IMPLEMENTED` | Estimated values | `08`, `13` |
| Per-tenant model configuration | `NOT_IMPLEMENTED` | Model table unused | `11` |
| Groundedness/factuality verification | `NOT_IMPLEMENTED` | Citation IDs checked, claims not | `08`, `13` |
| Evaluation harness and dataset | `NOT_IMPLEMENTED` | Empty evaluation test package | `13` |

## 6. API and browser UI

| Missing capability | Status | Evidence / notes | Required by |
|---|---|---|---|
| Browser upload UI | `NOT_IMPLEMENTED` | API only | `16` |
| Browser chat interface | `NOT_IMPLEMENTED` | API only | `16` |
| Citation viewer | `NOT_IMPLEMENTED` | API returns citations; no viewer | `16` |
| Feedback UI | `NOT_IMPLEMENTED` | API only | `16` |
| Ingestion status UI | `NOT_IMPLEMENTED` | API only | `16` |
| Document permission UI | `NOT_IMPLEMENTED` | API only | `16` |
| Admin dashboard/actions | `PARTIALLY_COMPLIANT` | Basic dashboard counts only | `16` |
| MFA prompts | `NOT_IMPLEMENTED` | No MFA | `16` |
| Loading/empty/error/success UX states | `PARTIALLY_COMPLIANT` | Templates are minimal | `16` |
| HTMX interactions | `NOT_IMPLEMENTED` | No HTMX usage found | `16` |
| Root route correctness | `NON_COMPLIANT` | `request.cookies.et(` | `16` |

## 7. Observability and operations

| Missing capability | Status | Evidence / notes | Required by |
|---|---|---|---|
| Structured request logs | `NOT_IMPLEMENTED` | Basic logger only | `14` |
| OpenTelemetry tracing | `NOT_IMPLEMENTED` | No instrumentation | `14` |
| Langfuse integration | `NOT_IMPLEMENTED` | No client/dependency usage | `14` |
| RAG-stage metrics | `NOT_IMPLEMENTED` | No metrics | `14` |
| Latency/error/cost dashboards | `NOT_IMPLEMENTED` | Only basic admin aggregates | `14` |
| Alerting thresholds | `NOT_IMPLEMENTED` | No alert configuration | `14` |
| CI/CD pipeline | `NOT_IMPLEMENTED` | No workflow config found | `15` |
| Nginx/TLS terminator | `NOT_IMPLEMENTED` | Compose has no Nginx | `15` |
| Migration deployment job | `NOT_IMPLEMENTED` | No migration command/service | `15` |
| Restricted datastore exposure | `NON_COMPLIANT` | Ports published; Redis/Qdrant unauthenticated | `10`, `15` |

## 8. Testing

| Missing capability | Status | Evidence / notes | Required by |
|---|---|---|---|
| Authorization/ACL tests | `NOT_IMPLEMENTED` | No tests | `13`, `18` |
| Cross-tenant tests | `NOT_IMPLEMENTED` | No integration/security tests | `13` |
| Database integration tests | `NOT_IMPLEMENTED` | `app/tests/integration/` empty | `13`, `18` |
| Qdrant/MinIO/Redis integration tests | `NOT_IMPLEMENTED` | None | `13`, `18` |
| Prompt-injection/security tests | `NOT_IMPLEMENTED` | None | `13` |
| Retrieval evaluation tests | `NOT_IMPLEMENTED` | None | `13` |
| API contract tests | `NOT_IMPLEMENTED` | Smoke health test only | `06`, `13` |
| Migration schema test | `NOT_IMPLEMENTED` | No migrations | `15` |
| Reproducible dev dependency install | `NON_COMPLIANT` | Invalid `httpx2` | `18`, `15` |

## 9. Documentation gaps

| Gap | Status | Notes |
|---|---|---|
| `06` permission/contract inconsistencies | Open | Analytics, ACL, ingestion listing, upload-path section |
| `03` role coverage | Open | Super-admin not implemented; department manager duties not enforceable |
| `08` sparse/streaming claims | Open | PostgreSQL FTS and simulated SSE differ |
| `09` sparse-vector design | Open | No Qdrant sparse vectors |
| `15` deployment topology | Open | No Nginx/migrations/secret workflow |
| `16` remaining screens | Acknowledged | Document explicitly lists missing browser screens |
| `README.md` | Stale | Says retrieval/generation are future work; models/migrations do not exist |
| `requirements-traceability-matrix.md` | Overstated | “Test coverage” column describes intended, not actual, coverage |

## 10. Summary

The largest missing areas are not the RAG algorithms. They are the production and trust layer:

1. Schema/migration/bootstrap.
2. Secret/configuration hardening.
3. Scope-correct authorization.
4. Audit, rate limiting, malware scanning, CSRF, MFA.
5. Evaluation and observability.
6. Super-admin/multi-tenant provisioning.
7. Integration/security tests.
8. Browser workflows.

Until these are addressed, the implementation should be treated as a development foundation rather than an enterprise-ready platform.

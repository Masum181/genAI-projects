# Documentation Compliance Matrix

**Audit date:** 2026-11-12  
**Sources of truth:** `docs/01-*` through `docs/21-*`, plus `data-dictionary.md`, `state-machines.md`, `requirements-traceability-matrix.md`  
**Legend:** `COMPLIANT` — implemented as documented; `PARTIALLY_COMPLIANT` — implemented with material gaps; `NON_COMPLIANT` — documented requirement not met; `NOT_IMPLEMENTED` — no implementation; `NOT_VERIFIABLE` — runtime evidence unavailable; `UNDOCUMENTED_BEHAVIOR` — behavior exists but is not described or conflicts with docs.

## 1. Document-by-document matrix

| Document | Status | Implemented evidence | Material gaps |
|---|---|---|---|
| `01-project-overview.md` | Partially compliant | Multi-tenant RAG domain, ingestion, retrieval, generation, citations, auth | Audit, observability, evaluation, production-grade security incomplete |
| `02-software-requirements-specification.md` | Partially compliant | Auth, documents, ingestion, chat, conversations, feedback, analytics, API keys | NFRs for rate limits, audit, evaluation, availability, RLS not met |
| `03-roles-and-permissions.md` | Partially compliant | Role defaults for organization admin, department manager, employee; permission sets seeded | No super-admin role; department scope not enforced in document management; unused permissions; enumeration gaps |
| `04-system-architecture.md` | Partially compliant | Modular monolith; API → service → repository layering; async SQLAlchemy; Qdrant/MinIO/Redis/Celery adapters | No RLS, no observability stack, no transaction/UoW convention, ad hoc authorization |
| `05-database-design.md` | Partially compliant | 21 ORM models matching documented entities; indexes and status constraints in several tables | No Alembic revisions; `memberships.role_id` lacks FK; some lifecycle/status gaps |
| `06-api-design.md` | Partially compliant | Auth, organizations, users, departments, documents, ingestion, chat, conversations, feedback, analytics, admin routes | Doc inconsistencies; simulated SSE; no idempotency; contract/security details incomplete |
| `07-document-ingestion.md` | Partially compliant | PDF/DOCX/XLSX/HTML/TXT extraction, chunking, embedding, Qdrant indexing, Celery retries | No OCR fallback, malware scan, semantic/structure-aware chunking, cleanup/reindex task types |
| `08-rag-pipeline.md` | Partially compliant | Dense + PostgreSQL full-text sparse retrieval, RRF, cross-encoder rerank, grounded prompt, citation ID validation | Query rewrite/routing, context compression, reranker confidence threshold, true streaming, evaluation missing |
| `09-vector-database-design.md` | Partially compliant | One dense collection, cosine, payload indexes, deterministic point IDs, tenant/document/version filters | Sparse vectors are not stored in Qdrant; no snapshot/restore/operations tooling |
| `10-security-and-privacy.md` | Non-compliant | Password hashing, JWT, API keys, server-resolved tenant, ACL deny precedence, prompt isolation | No MFA, rate limiting, CSRF, malware scanning, audit writes, RLS; default secret; several authorization defects |
| `11-llm-and-prompt-design.md` | Partially compliant | Ollama/OpenAI/Gemini adapters, grounded system prompt, JSON output, citation validation | `model_configurations` unused; no provider usage accounting; no confidence/refusal threshold policy |
| `12-background-processing.md` | Partially compliant | Celery ingestion task, retries, failure/dead-letter persistence, engine disposal | No cleanup/reindex/metrics tasks; no idempotency key; vector/DB consistency risks |
| `13-evaluation-and-testing.md` | Not implemented | Only 24 unit/smoke tests | No golden dataset, Recall@K/Precision@K/MRR/NDCG, groundedness, citation accuracy, security, or integration suites |
| `14-observability-and-monitoring.md` | Not implemented | Basic Python logging and health endpoints | No metrics, tracing, latency histograms, token/cost dashboards, alerting, or Langfuse/OpenTelemetry |
| `15-deployment-and-devops.md` | Non-compliant | Dockerfile and Compose for API, worker, PostgreSQL, Redis, Qdrant, MinIO | No migrations/bootstrap, no Nginx/TLS, exposed datastore ports, Redis/Qdrant unauthenticated, credential mismatches |
| `16-frontend-ux-specification.md` | Partially compliant | Jinja2 login, dashboard, document list, conversation list, logout | No upload, chat, citation viewer, department/user admin, HTMX interactions, toasts, loading states |
| `17-business-workflows.md` | Partially compliant | Registration, invitation, upload/ingestion, access assignment, QA, conversations, feedback, replacement/deletion | Registration creates org admin not super admin; no department membership management; no org suspension workflow; audit absent |
| `18-project-structure-and-coding-standards.md` | Partially compliant | Directory layout, service/repository separation, Pydantic schemas, centralized exception handling | Authorization centralized inconsistently; transaction boundaries leak; monitoring module empty; tests insufficient |
| `19-implementation-roadmap.md` | Partially compliant | Phases 1–6 have substantial implementation | Evaluation, monitoring, hardening, and production readiness phases incomplete |
| `20-risks-and-architecture-decisions.md` | Partially compliant | Some mitigations present: ACL filters, prompt isolation, deterministic IDs, soft delete | Cross-tenant/RLS, audit, malware, retention, restore, and evaluation risks remain open |
| `21-glossary-and-references.md` | Compliant | Terminology aligns with code for main domain terms | No material gap |
| `data-dictionary.md` | Partially compliant | Core fields and entities match models | Some relationships/lifecycle semantics undocumented |
| `state-machines.md` | Partially compliant | Document/job status values exist; retries and dead-letter path implemented | Validation state is not modelled; conversation archival only via API update; document archived state not fully driven |
| `requirements-traceability-matrix.md` | Partially compliant | Rows map to real endpoints/entities | “Test coverage” column overstates current coverage |

## 2. API contract consistency

| Contract claim | Implementation | Result |
|---|---|---|
| `POST /documents/upload` | `app/api/v1/documents.py:56` | Aligned with later section of `06-api-design.md` |
| Nested organization upload path in earlier section | Not implemented | Documentation inconsistency; later section documents the actual route |
| Analytics requires `analytics:read_org` | Code also accepts `analytics:read_department` while querying org-wide | Documentation/implementation mismatch and confidentiality defect |
| Delete/ACL management requires `document:manage_org` | Code accepts `document:manage_department` without target scope | Documentation/implementation mismatch and authorization defect |
| Ingestion job listing is owner/admin-only | Code allows any principal authorized to read the document | Documentation inconsistency; implementation is broader |
| SSE streaming | Response is generated before the stream starts, then split into 80-character events | Contract shape present; streaming semantics not met |
| Document upload returns 409 for duplicate content | Returns existing document ID in the error detail | Contract adds an information disclosure |
| Registration creates super admin | Creates `organization_admin` only | Workflow/role documentation mismatch |

## 3. Requirement traceability status

| Requirement | Documented intent | Current status | Evidence / gap |
|---|---|---|---|
| FR-AUTH-001 secure authentication | Login, tokens, hashing | `PARTIALLY_COMPLIANT` | Auth implemented; default secret, no MFA, no rate limiting |
| FR-ORG-001 multi-org isolation | Cross-tenant isolation | `PARTIALLY_COMPLIANT` | Application filters present; no RLS; second-org creation unreachable |
| FR-DOC-001 document upload | Secure uploaded documents | `PARTIALLY_COMPLIANT` | Upload implemented; no malware scan; scope defects |
| FR-ING-002 async ingestion | Worker task queue | `COMPLIANT` | Celery worker with retries and status tracking |
| FR-RAG-001 dense retrieval | Dense retrieval | `COMPLIANT` | Qdrant dense search with tenant/document/version filters |
| FR-RAG-003 hybrid retrieval | Hybrid retrieval | `PARTIALLY_COMPLIANT` | Dense + PostgreSQL full-text + RRF; sparse is not Qdrant/BM25 |
| FR-CHAT-003 citation-backed answers | Verified citations | `PARTIALLY_COMPLIANT` | ID/excerpt validation exists; not full factual grounding |
| FR-SEC-001 audit logging | Audit events | `NON_COMPLIANT` | Model exists; no writes |
| FR-EVAL-001 retrieval evaluation | Offline benchmark | `NOT_IMPLEMENTED` | No dataset, metrics, or harness |
| FR-MON-001 usage monitoring | Dashboards and metrics | `PARTIALLY_COMPLIANT` | Basic admin aggregates only; no monitoring stack |
| `13` security evaluation | Cross-tenant, injection, deletion tests | `NOT_IMPLEMENTED` | Security test directory empty |
| `10` audit fields | Request/user/org/action/result/IP | `NON_COMPLIANT` | No audit write path |

## 4. Highest-priority compliance corrections

1. Add initial migration and schema verification to satisfy `05` and `15`.
2. Make production configuration fail closed for missing secrets and fix `.env.example`.
3. Align `03`, `06`, and implementation for analytics, document ACL, and ingestion permissions.
4. Enforce department scope in document upload, metadata update, version upload, deletion, and ACL changes.
5. Implement audit writes and security-event coverage required by `10`.
6. Implement the testing and evaluation requirements in `13`.
7. Implement the observability requirements in `14`.
8. Bring deployment into line with `15` (TLS terminator, restricted ports, authenticated Redis/Qdrant, migration job).

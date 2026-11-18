# Critical Issues

**Audit date:** 2026-11-12  
**Scope:** Critical and high-severity findings, plus medium findings that materially affect security, correctness, or operability  
**Status basis:** Static review; runtime verification unavailable because dependencies and services are not installed/running

## 1. Critical findings

### C-01 — No database schema bootstrap or Alembic revisions

- **Severity:** CRITICAL
- **Status:** NON_COMPLIANT
- **Evidence:** `alembic/versions/` contains only `__init__.py` and `.gitkeep`; `app/database/init_db.py` is a docstring-only stub; `app/database/session.py:27-31` only executes `SELECT 1`; `app/main.py:31-36` calls only `check_database_connection()`.
- **Impact:** A fresh deployment has no application tables. Migrations are documented as required but cannot create the schema. `/ready` can return 200 against an empty but reachable database, producing a false-positive readiness signal.
- **Remediation:** Generate and commit an initial Alembic migration covering all 21 models. Add a deployment migration step before starting API/worker. Consider a startup schema-version check that fails closed.

### C-02 — Known default JWT secret; `.env.example` omits `APP_SECRET_KEY`

- **Severity:** CRITICAL
- **Status:** NON_COMPLIANT
- **Evidence:** `app/core/config.py:27` sets `secret_key = "change-this-secret-before-deployment"`; `.env.example` has no `APP_SECRET_KEY` entry.
- **Impact:** Deployments that copy `.env.example` use a public, predictable signing key. An attacker who knows a valid user and organization ID can forge access or refresh tokens; with the default key, token confidentiality and identity integrity are lost.
- **Remediation:** Remove the production default, require a non-placeholder secret at startup, add `APP_SECRET_KEY` to `.env.example` with a clear placeholder, and validate minimum entropy/length.

## 2. High-severity findings

### H-01 — Department managers can upload into arbitrary departments

- **Severity:** HIGH
- **Status:** NON_COMPLIANT / UNDOCUMENTED_BEHAVIOR
- **Evidence:** `department_manager` includes `document:upload` at `app/services/auth_service.py:51`; `upload_document` checks only that the requested department exists in the tenant at `app/services/document_service.py:159-164`.
- **Impact:** A manager for department A can place content into department B. Combined with department-based ACLs, this can move sensitive content into a scope the manager does not govern, or create misleading ownership metadata.
- **Remediation:** Require organization-level management authority for arbitrary departments, or verify the caller manages the requested department.

### H-02 — `_can_manage` does not enforce target department scope

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** `app/services/document_service.py:56-60` checks only `document:manage_org` or `document:manage_department`; update (`:314-339`), delete (`:341-386`), version upload, and ACL replacement (`:393-442`) then operate on any document returned by `get_authorized_document`.
- **Impact:** A department manager with read access to another department’s document via an explicit user grant can update, delete, version, or rewrite ACLs for that document. “Manage department” becomes “manage anything readable.”
- **Remediation:** Resolve the caller’s managed department IDs and require the target document’s `department_id` to be in that set; reserve org-wide management for `document:manage_org`/administrators.

### H-03 — Organization-wide ACL grants can be created by any document manager

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** `DocumentPermissionInput.grant_type` permits `"organization"` at `app/schemas/requests.py:93-98`; `replace_document_permissions` skips target validation for organization grants and writes the record at `app/services/document_service.py:407-438`.
- **Impact:** A department manager can make a document readable by the entire tenant. This is a privilege escalation relative to department-scoped authority and can expose sensitive content broadly.
- **Remediation:** Require `document:manage_org` or organization-admin authority for `grant_type="organization"`; reject organization grants from department managers.

### H-04 — Analytics permission is department-scoped but data is organization-wide

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** `_authorize_analytics` accepts `analytics:read_department` at `app/services/analytics_service.py:12-18`; `usage_summary`, `documents_by_status`, and `ingestion_by_status` query only `principal.organization_id` at `:31`, `:46-47`.
- **Impact:** A department manager can view tenant-wide usage, token/cost totals, document counts, and ingestion status instead of their department’s data.
- **Remediation:** Add department-scoped analytics queries and require `analytics:read_org` for tenant-wide results.

### H-05 — No audit-log write path

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** `app/models/audit_log.py` defines the entity and `app/repositories/audit_repository.py` only counts events; no service, API, worker, or middleware creates `AuditLog` rows.
- **Impact:** Security-relevant actions (login, failed authorization, uploads, deletions, ACL changes, admin actions, invitation/disable events) are untraceable. This violates the audit requirements and weakens incident response.
- **Remediation:** Add an audit service/middleware and write structured events transactionally or via an outbox. Include request ID, user/org, action, target, result, IP, and relevant metadata.

### H-06 — Required security controls are absent

- **Severity:** HIGH
- **Status:** NOT_IMPLEMENTED
- **Evidence:** No MFA challenge flow; no rate-limiting middleware/dependency; no CSRF token mechanism; `app/utils/file_validation.py` checks extension and size only; no malware/quarantine integration; no `Idempotency-Key` handling.
- **Impact:** Privileged accounts rely on passwords only; login/chat/upload abuse is unthrottled; cookie-authenticated browser mutations are CSRF-exposed; malicious uploads reach extraction/indexing; retries can duplicate side effects.
- **Remediation:** Add MFA/TOTP for privileged roles, tenant/user/route rate limits, CSRF tokens or strict custom-header requirements for cookie sessions, malware scanning/quarantine before processing, and idempotency keys for mutating endpoints.

### H-07 — Super-administrator and second-tenant paths are unreachable

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** Initial registration creates an `organization_admin` membership (`app/repositories/auth_repository.py:79`); no `super_admin` role is seeded. `create_organization` requires `principal.is_super_admin` (`app/services/organization_service.py:34-38`), and `is_super_admin` requires the `super_admin` role (`app/core/identity.py:24-25`).
- **Impact:** Only one organization can be created through the API. Platform administration cannot be bootstrapped without manual database manipulation. Multi-tenant SaaS operation is not viable.
- **Remediation:** Define a supported platform-admin bootstrap path (CLI or controlled provisioning), seed the role/permissions, and add tests for second-tenant creation.

### H-08 — Department/member enumeration by any authenticated tenant user

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** `list_departments` and `list_department_members` perform only tenant resolution (`app/services/department_service.py:26-43`, `:130-150`); no permission check is applied.
- **Impact:** Any employee can enumerate the tenant’s department structure and member names/emails, aiding social engineering and leaking organizational structure.
- **Remediation:** Require `department:read_self` plus membership/authority checks, or restrict member listing to department managers and administrators.

### H-09 — Duplicate upload response discloses an existing document ID

- **Severity:** HIGH
- **Status:** UNDOCUMENTED_BEHAVIOR
- **Evidence:** `find_duplicate` returns a document ID (`app/repositories/document_repository.py:35-42`); `upload_document` returns HTTP 409 with `existing document is {duplicate_id}` (`app/services/document_service.py:162-168`).
- **Impact:** A user without access to a document can confirm its existence and learn its identifier by uploading identical content. This is an object-existence oracle.
- **Remediation:** Return a generic duplicate message without the ID, or omit duplicate detection detail for unauthorized documents.

### H-10 — Browser `GET /` raises `AttributeError`

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** `app/web.py:22` calls `request.cookies.et("access_token")`.
- **Impact:** The root URL fails for every browser request, breaking the normal entry point.
- **Remediation:** Change to `request.cookies.get("access_token")` and add a route test.

### H-11 — Evaluation is not implemented

- **Severity:** HIGH
- **Status:** NOT_IMPLEMENTED
- **Evidence:** `app/tests/evaluation/` contains only `__init__.py`; no benchmark dataset, retrieval metrics, groundedness, citation accuracy, or regression harness exists.
- **Impact:** Retrieval/generation quality and regressions cannot be measured. The design’s core quality claims are unverified.
- **Remediation:** Add a labelled golden dataset, Recall@K/Precision@K/MRR/NDCG, citation accuracy, groundedness review, and CI thresholds.

### H-12 — Observability is not implemented

- **Severity:** HIGH
- **Status:** NOT_IMPLEMENTED
- **Evidence:** `app/monitoring/` contains only `__init__.py`; no structured request logging, OpenTelemetry spans, metrics, dashboards, or Langfuse integration.
- **Impact:** Latency, queue depth, token spend, error rates, and RAG stage failures cannot be monitored or alerted on.
- **Remediation:** Add structured logging with request/tenant/user correlation, OpenTelemetry tracing across API/worker/RAG, metrics, dashboards, and alert thresholds.

### H-13 — Deployment configuration is insecure and not runnable as documented

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** `docker-compose.yml` exposes PostgreSQL 5432, Redis 6379, Qdrant 6333/6334, and MinIO 9000/9001; no Redis password, Qdrant API key, or Nginx service; `.env.example` storage credentials do not match MinIO root credentials and are not overridden by Compose; `POSTGRES_*` values do not match the host `DATABASE_URL`.
- **Impact:** Local setup fails or silently uses wrong credentials; deployed infrastructure is directly reachable; Redis/Qdrant are unauthenticated; TLS termination is absent.
- **Remediation:** Add Nginx/TLS, restrict published ports to localhost or remove them, authenticate Redis/Qdrant, align storage credentials, reconcile `DATABASE_URL` with `POSTGRES_*`, and add a migration job.

### H-14 — Required test coverage is absent

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** 24 test functions total; no authorization, ACL, cross-tenant, API integration, database, security, or evaluation tests. `app/tests/integration/`, `security/`, and `evaluation/` are empty.
- **Impact:** The most dangerous defects in this report would not be caught by the suite. Tenant isolation and permission regressions are unprotected.
- **Remediation:** Add service-level permission tests and API/DB integration tests for tenant, department, ACL allow/deny, admin bypass, and deletion/revocation flows.

### H-15 — Developer setup dependency is invalid

- **Severity:** HIGH
- **Status:** NON_COMPLIANT
- **Evidence:** `pyproject.toml:40` declares `httpx2>=2.0,<3`; no such package is expected by the test stack, while `fastapi.testclient` requires `httpx`. `httpx` is absent from `requirements.txt`.
- **Impact:** The documented `.[dev]` install can fail; even if installed another way, smoke/API tests cannot import `TestClient`.
- **Remediation:** Replace `httpx2` with `httpx`, align root and app dependency mirrors, and verify installation in a clean environment.

### H-16 — Department managers cannot perform documented department maintenance

- **Severity:** HIGH
- **Status:** PARTIALLY_COMPLIANT
- **Evidence:** `department_manager` has `department:update_self` and `user:manage_department` (`app/services/auth_service.py:47-59`), but `department_service._can_manage` requires `department:manage_org` (`app/services/department_service.py:17-18`), and `invite_user` requires `user:invite` (`app/services/user_service.py:56`).
- **Impact:** Department managers cannot update their department or manage department membership despite documented duties. There is also no add/remove-member endpoint for existing users.
- **Remediation:** Implement department-scoped authority checks and membership management endpoints; define whether managers may invite users or only assign existing users.

## 3. Medium findings

| ID | Finding | Evidence | Impact | Remediation |
|---|---|---|---|---|
| M-01 | Uploads do not create a default department ACL | `app/services/document_service.py:145-230`; `DocumentPermission` created only by ACL replacement | Department members cannot read a department-tagged document unless an ACL is added afterward; behavior contradicts department-scoped expectations | Create a default department `read` grant on upload, or document default-deny explicitly |
| M-02 | `memberships.role_id` has no foreign key | `app/models/membership.py:24` | Orphaned/invalid role references; joins resolve no permissions | Add `ForeignKey("roles.id")` and a migration |
| M-03 | No RLS in PostgreSQL | Models and repositories use application filters; no policies found | A repository/query mistake could cross tenants | Add RLS policies keyed by tenant context as defense in depth |
| M-04 | Deleted documents retain object storage and possibly vectors | `delete_document` soft-deletes DB then deletes vectors (`app/services/document_service.py:341-386`); no `MinioStorage.delete` call | Storage retention/cost and secure-deletion non-compliance; Qdrant failure leaves orphan vectors | Add retention/secure-deletion workflow and cleanup/outbox jobs |
| M-05 | Ingestion removes old vectors before chunk persistence | `app/workers/ingestion_worker.py:95-125` | A persistence failure can leave the document indexed with no or partial vectors | Persist chunks and swap `current_version_id` transactionally, then clean old vectors |
| M-06 | SSE is simulated, not true streaming | `app/api/v1/chat.py:63-91` generates the full answer before yielding | Perceived latency equals full generation; clients cannot consume real token deltas | Stream from provider through the endpoint, then persist |
| M-07 | Token usage is estimated, not provider-reported | `app/services/chat_service.py:160-171` uses character-length heuristics; chunk `token_count` is a word count (`app/rag/chunkers/fixed_chunker.py:33`) | Cost/token analytics are inaccurate | Capture provider usage metadata; use a real tokenizer |
| M-08 | No idempotency enforcement | No `Idempotency-Key` handling found | Retries can duplicate uploads, messages, jobs, or usage records | Add idempotency records and replay semantics for mutations |
| M-09 | Sparse retrieval is PostgreSQL full-text, not Qdrant sparse vectors/BM25 | `app/repositories/document_repository.py:71-101` | Design’s sparse-vector/Qdrant operational model is not realized; performance/recall may differ | Either align docs or implement Qdrant sparse vectors/BM25 |
| M-10 | Query rewrite/routing absent | `app/services/retrieval_service.py:20-22` normalizes NFKC/whitespace only | Poor recall for abbreviations, ambiguity, and policy lookup patterns | Add configurable rewrite/routing with safe fallbacks |
| M-11 | No reranker confidence threshold | `app/services/retrieval_service.py:98-99` always returns top results | Irrelevant evidence can reach generation even when scores are poor | Add score/confidence thresholds and an insufficient-evidence path |
| M-12 | Qdrant/reranker failures are not mapped to graceful responses | Only `EmbeddingProviderError` and `LLMProviderError` are mapped in `app/services/chat_service.py:69-105` | Provider outages can surface as unhandled 500s instead of controlled 503/degraded responses | Map retrieval/reranker failures to consistent 503/insufficient-evidence behavior |
| M-13 | No model configuration use | `app/models/model_configuration.py`; no runtime references | Per-tenant/default model settings cannot be managed despite schema | Wire configuration into factory/selection or remove the unused model |
| M-14 | No security headers/CORS policy | `app/main.py` adds only request-ID middleware | Missing standard hardening and cross-origin policy | Add security headers and explicit CORS configuration |
| M-15 | Client-supplied request IDs are trusted | `app/middleware/request_id.py:20-21` | Log injection/correlation spoofing; control characters retained | Validate/limit charset, or generate server IDs and retain client ID separately |
| M-16 | No object-storage purge on user deletion/retention | `delete_user` disables user only (`app/services/user_service.py:150-166`); no retention job | Data-retention/privacy obligations unmet | Add retention policy, deletion workflow, and storage/vector cleanup |
| M-17 | No CI/pre-commit config | No CI workflow or pre-commit config found | Lint/type/schema/test regressions are not gated | Add CI with compile, lint, tests, migration check, and security tests |
| M-18 | Documentation and code disagree on several permissions/contracts | See `02-documentation-compliance-matrix.md` | Operators and clients may implement the wrong policy | Update `03`, `06`, and implementation together; add contract tests |

## 4. Positive findings worth preserving

- Server-resolved tenant context is consistently used for document/conversation queries.
- ACL filters include owner, user/department/organization grants, explicit deny precedence, and admin allow bypass without bypassing deny.
- Qdrant queries include organization, document, version, and deletion filters.
- Prompt construction isolates untrusted evidence and validates structured output.
- Refresh tokens rotate/revoke; API-key scopes are intersected with role permissions; API keys cannot become administrators.
- Password hashing uses PBKDF2-HMAC-SHA256 with a unique salt and constant-time verification.
- Ingestion has retry limits, failure persistence, dead-letter handling, and partial-vector cleanup.

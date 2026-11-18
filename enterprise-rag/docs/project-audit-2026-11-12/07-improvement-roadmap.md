# Improvement Roadmap

**Audit date:** 2026-11-12  
**Purpose:** Prioritized remediation plan based on the audit findings  
**Constraint:** This is a planning document only; no fixes were implemented during the audit

## 1. Prioritization model

| Priority | Meaning | Release gate |
|---|---|---|
| P0 | Blocks any usable or safe deployment | Must be fixed before any non-local use |
| P1 | Serious security, correctness, or operability risk | Must be fixed before production or multi-tenant use |
| P2 | Material product/quality gap | Should be fixed before general availability |
| P3 | Hardening, scale, and polish | Continuous improvement |

## 2. P0 — Make the platform bootable and fail-safe

### P0.1 Add the initial Alembic migration and schema bootstrap

- **Findings:** C-01
- **Work:**
  - Generate an initial migration covering all 21 models.
  - Verify constraints, indexes, FKs, and status checks.
  - Add a deployment migration step before API/worker start.
  - Add a startup or readiness check for expected schema revision.
  - Add a migration test on an empty PostgreSQL instance.
- **Acceptance criteria:**
  - `alembic upgrade head` creates the full schema from empty.
  - `/ready` fails when the schema revision is missing.
  - API and worker start only after a successful migration.
- **Dependencies:** none.

### P0.2 Remove the default JWT secret and fix configuration

- **Findings:** C-02, H-13
- **Work:**
  - Remove the production default or make the application refuse to start with it outside development.
  - Add `APP_SECRET_KEY` to `.env.example` with a clear placeholder.
  - Add minimum-length/entropy validation.
  - Reconcile `DATABASE_URL` with `POSTGRES_*`.
  - Align MinIO root credentials with `STORAGE_ACCESS_KEY`/`STORAGE_SECRET_KEY`, or inject them explicitly in Compose.
- **Acceptance criteria:**
  - Production startup fails closed without a strong secret.
  - Copied `.env.example` supports host and Compose workflows.
  - Uploads succeed against MinIO with the documented setup.
- **Dependencies:** none.

### P0.3 Fix the browser root route

- **Findings:** H-10
- **Work:** Correct `request.cookies.et(` to `request.cookies.get(` and add a route test.
- **Acceptance criteria:** `GET /` redirects to `/login` or `/ui/` without error.

## 3. P1 — Fix authorization and security boundaries

### P1.1 Implement resource-scoped document authorization

- **Findings:** H-01, H-02, H-03, M-01
- **Work:**
  - Create policy functions for document read/manage/ACL actions.
  - Enforce manager department scope for upload, metadata update, version upload, delete, and ACL changes.
  - Require organization-admin authority for organization-wide ACL grants.
  - Decide and implement the default department ACL behavior.
- **Acceptance criteria:**
  - Department manager cannot affect another department’s documents.
  - Department manager cannot create organization-wide grants.
  - Upload behavior for department documents matches documented policy.
  - Tests cover allow/deny for owner, same-department manager, other-department manager, admin, and explicit deny.
- **Dependencies:** migration (for any new constraints/rows), test harness.

### P1.2 Fix analytics and enumeration authorization

- **Findings:** H-04, H-08
- **Work:**
  - Add department filters for `analytics:read_department`; require `analytics:read_org` for org-wide data.
  - Protect department listing and member listing with explicit permissions/authority checks.
  - Add tests for department manager vs employee vs admin.
- **Acceptance criteria:**
  - Department managers see only their scope.
  - Employees cannot enumerate departments/members beyond documented access.
- **Dependencies:** P1.1 policy layer.

### P1.3 Add audit logging

- **Findings:** H-05
- **Work:**
  - Add an audit service/outbox.
  - Emit events for login success/failure, token/API-key events, authorization failures, uploads, deletions, ACL changes, role/status changes, admin actions, and ingestion failures.
  - Include request ID, user, organization, action, target, result, IP, and metadata.
- **Acceptance criteria:**
  - Security-relevant actions produce queryable audit rows.
  - Audit failure policy is explicit (fail closed for critical events or durable outbox).
- **Dependencies:** migrations.

### P1.4 Add missing security controls

- **Findings:** H-06
- **Work:**
  - MFA/TOTP for privileged roles.
  - Rate limiting per tenant/user/route with Redis.
  - CSRF protection for cookie-authenticated mutations, or require an explicit anti-CSRF header.
  - Malware scanning/quarantine before extraction.
  - Idempotency keys for uploads and other mutations.
- **Acceptance criteria:**
  - Privileged users can enroll and are challenged.
  - Login/chat/upload abuse is throttled.
  - Cookie mutations require a valid CSRF token/header.
  - Unsafe uploads are quarantined.
  - Replayed mutations do not duplicate side effects.
- **Dependencies:** configuration, migrations, infrastructure.

### P1.5 Fix super-admin and multi-tenant provisioning

- **Findings:** H-07
- **Work:**
  - Add a controlled platform-admin bootstrap (CLI/provisioning).
  - Seed `super_admin` role/permissions.
  - Add tests for second-organization creation and cross-tenant denial.
- **Acceptance criteria:**
  - A fresh installation can provision a platform admin.
  - A super admin can create a second organization.
  - Organization isolation remains enforced.
- **Dependencies:** migrations.

### P1.6 Repair test infrastructure and add security/integration coverage

- **Findings:** H-14, H-15
- **Work:**
  - Replace invalid `httpx2` with `httpx`.
  - Align root/app requirements and `pyproject.toml`.
  - Add a clean-install CI job.
  - Add service/API/database tests for tenancy, ACLs, roles, audit, deletion, and ingestion.
- **Acceptance criteria:**
  - `pip install -e ".[dev,ai]"` succeeds in a clean environment.
  - `pytest` runs without collection errors.
  - Tests prove cross-tenant and cross-department denial.
- **Dependencies:** dependency fix; database test fixture.

### P1.7 Harden deployment

- **Findings:** H-13
- **Work:**
  - Add Nginx/TLS termination.
  - Restrict published ports to localhost or remove them.
  - Authenticate Redis and Qdrant.
  - Add a migration job.
  - Add health/readiness probes and production configuration guidance.
- **Acceptance criteria:**
  - Production Compose/deployment does not expose datastores publicly.
  - TLS terminates at the reverse proxy.
  - Migrations run before API/worker.
- **Dependencies:** P0.1, P0.2.

## 4. P2 — Correct data and RAG quality behavior

### P2.1 Make cross-store operations recoverable

- **Findings:** M-04, M-05, M-08
- **Work:**
  - Introduce explicit transaction boundaries in services.
  - Persist chunk/version state and vector cleanup intents transactionally.
  - Add idempotent cleanup jobs for orphaned MinIO objects/vectors.
  - Purge object storage on deletion/retention.
- **Acceptance criteria:**
  - Retried ingestion/deletion converges to a consistent state.
  - No orphaned objects/vectors remain after cleanup.
  - Deletion satisfies retention policy.
- **Dependencies:** migrations, worker changes.

### P2.2 Improve retrieval failure handling and confidence

- **Findings:** M-11, M-12
- **Work:**
  - Map Qdrant/reranker failures to documented degraded responses.
  - Add dense-only fallback when sparse fails.
  - Add reranker score threshold and insufficient-evidence decision.
  - Warm the reranker and enforce timeouts.
- **Acceptance criteria:**
  - External failures return controlled 503/insufficient-evidence responses.
  - Low-confidence evidence does not produce an answered response.
- **Dependencies:** retrieval service refactor.

### P2.3 Fix token accounting and true streaming

- **Findings:** M-06, M-07
- **Work:**
  - Use a real tokenizer for chunk counts and context budgeting.
  - Capture provider-reported usage where available.
  - Stream provider output through SSE, then persist the final assistant message/citations.
- **Acceptance criteria:**
  - Token metrics align with provider usage within tolerance.
  - SSE delivers progressive tokens before generation completes.
- **Dependencies:** provider adapters, persistence refactor.

### P2.4 Implement evaluation

- **Findings:** H-11
- **Work:**
  - Build a labelled golden dataset.
  - Add Recall@K, Precision@K, MRR, NDCG, citation accuracy, and groundedness checks.
  - Add regression thresholds to CI.
  - Add prompt-injection and deletion/revocation security evaluations.
- **Acceptance criteria:**
  - Evaluation runs on every retrieval/model change.
  - Regressions fail CI or produce a documented report.
- **Dependencies:** stable retrieval/generation interfaces.

### P2.5 Implement observability

- **Findings:** H-12
- **Work:**
  - Structured request logs with request/tenant/user/route/status/duration.
  - OpenTelemetry spans for API, auth, retrieval stages, LLM calls, and ingestion.
  - Metrics for latency, errors, queue depth, token usage, cost, and dead letters.
  - Dashboards and alerts for the documented thresholds.
- **Acceptance criteria:**
  - A request can be traced end-to-end by request ID.
  - Dashboards expose the documented metrics.
- **Dependencies:** deployment, configuration.

### P2.6 Align sparse retrieval and chunking with design

- **Findings:** M-09, M-10
- **Work:**
  - Either implement Qdrant sparse vectors/BM25 or document PostgreSQL FTS as the chosen design.
  - Add token/structure-aware chunking and heading/table preservation.
  - Add query rewrite/routing with safe fallbacks.
- **Acceptance criteria:**
  - Design docs and implementation agree.
  - Retrieval evaluation shows no regression on exact-term/acronym queries.
- **Dependencies:** evaluation harness.

## 5. P3 — Product completion and hardening

### P3.1 Complete browser workflows

- Upload and ingestion status.
- Chat and citation viewer.
- Feedback interface.
- Document permission management.
- Admin dashboard and safe actions.
- Loading/empty/error/success states.
- MFA prompts and UX.

### P3.2 Complete organization/department management

- Department membership add/remove.
- Super-admin organization lifecycle.
- Role/permission management.
- Organization suspension with explicit session revocation and audit.

### P3.3 Improve database integrity

- Add `memberships.role_id` FK.
- Review tenant columns on join-only tables.
- Add RLS policies.
- Add lifecycle/status constraints and missing indexes.

### P3.4 Add deployment and operations automation

- CI/CD with lint, tests, migration check, image build, staging deploy.
- Backup/restore drills.
- Retention jobs.
- Qdrant snapshot/restore procedures.
- Re-embedding/reindex runbook and tooling.

### P3.5 Clean documentation

- Correct `06` permission/endpoint inconsistencies.
- Correct `08` sparse/streaming claims.
- Correct `09` sparse-vector claims.
- Correct `15` deployment topology.
- Update `README.md` to reflect implemented RAG and migration status.
- Update the traceability matrix’s test-coverage column to actual coverage.

## 6. Suggested delivery sequence

1. **Boot and secrets:** P0.1, P0.2, P0.3.
2. **Authorization and audit:** P1.1, P1.2, P1.3.
3. **Security controls and provisioning:** P1.4, P1.5.
4. **Test and deployment gates:** P1.6, P1.7.
5. **Data consistency and RAG quality:** P2.1, P2.2, P2.3.
6. **Evaluation and observability:** P2.4, P2.5.
7. **Search/chunking alignment:** P2.6.
8. **Product/UI and operations:** P3.

## 7. Release gates

### Gate A — Local development usable

- P0 complete.
- Clean install succeeds.
- Browser login and root route work.
- Upload/ingestion can complete locally.

### Gate B — Security review ready

- P1.1–P1.6 complete.
- Cross-tenant/department tests pass.
- Audit events are emitted.
- No default secrets.

### Gate C — Production readiness

- P1.7 and P2.1–P2.5 complete.
- Migrations run automatically.
- Rate limits/CSRF/MFA/malware controls active.
- Evaluation and observability gates pass.
- Backup/restore/rollback rehearsed.

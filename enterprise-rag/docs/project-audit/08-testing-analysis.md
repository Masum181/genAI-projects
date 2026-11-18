# 08 — Testing Analysis

## 1. Summary

The repository has 16 test functions in 7 files. The existing tests are thoughtful but narrow: token integrity, model registration, Qdrant collection setup, architecture boundaries, template path resolution, route mounting, and health/readiness. There are no tests for services, repositories, authorization, tenant isolation, uploads, ACLs, chat, migrations, workers, or the browser home route. Integration, security, and evaluation directories exist but are empty.

**Testing verdict:** insufficient for a production RAG platform. The current suite could pass while the product’s core workflows are broken.

## 2. Test inventory

| File | Tests | What it covers |
|---|---:|---|
| `tests/test_health.py` | 3 | `/health`, `/ready` success, DB failure -> 503 |
| `app/tests/unit/test_auth_token.py` | 3 | Claims, tamper rejection, token-type rejection |
| `app/tests/unit/test_config.py` | 1 | Basic local defaults |
| `app/tests/unit/test_layering.py` | 2 | API→DB and service→API/DB architecture checks |
| `app/tests/unit/test_models.py` | 3 | Exact table set, metadata column, UUIDv7 |
| `app/tests/unit/test_qdrant.py` | 2 | Collection creation/indexes, dimension mismatch |
| `app/tests/unit/test_web.py` | 2 | Login template renders from another cwd; routes mounted |
| **Total** | **16** | |

Empty suites:

- `app/tests/integration/` — only `__init__.py`
- `app/tests/security/` — only `__init__.py`
- `app/tests/evaluation/` — only `__init__.py`

## 3. Execution status in the audit environment

Command attempted:

```bash
python3 -m pytest -q
```

Result: exit code 2, six collection errors. Failures are environmental, not necessarily code failures:

- `fastapi` not installed
- `qdrant_client` not installed
- other project dependencies not installed
- pytest warns `Unknown config option: asyncio_mode` because `pytest-asyncio` is absent
- the available interpreter is Python 3.14 while the project declares 3.11+

A separate non-mutating check succeeded:

```bash
python3 -m compileall -q app alembic
# exit code 0
```

This proves syntax/importability at compile level, not runtime correctness. The audit did not install dependencies, per scope constraints.

## 4. What the current tests do well

1. **Token tampering is tested.** Signature changes and wrong token type are rejected.
2. **Architecture direction is tested.** Direct session calls in routes and API imports in services are caught.
3. **Exact model set is tested.** Adding/removing a table requires an explicit test update.
4. **Qdrant setup is tested.** Collection creation, payload indexes, and dimension mismatch are covered.
5. **Template path portability is tested.** The login template renders from a temporary working directory.
6. **Route mounting is tested.** Critical API and UI paths must be registered.
7. **Readiness failure is tested.** Database failure maps to 503.
8. **Tests avoid real infrastructure.** Defaults are mocked; the suite can run quickly when dependencies exist.

## 5. Critical coverage gaps

### 5.1 Browser home route (High)

No test calls `GET /`. The confirmed `request.cookies.et` typo would have been caught by a one-line test:

```python
with TestClient(app) as client:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
```

### 5.2 Authentication service flows (High)

No tests for:

- First organization registration and one-time closure
- Login with zero, one, or multiple organization candidates
- Inactive user/organization/membership rejection
- Refresh, revocation, and rotation race
- Invitation acceptance, expiry, and single use
- API-key creation scopes, expiry, revocation, and use
- Principal resolution from cookie, bearer, and API key
- Role/permission loading and tenant consistency

### 5.3 Authorization and tenant isolation (High)

No negative tests for:

- Employee listing departments/members
- Employee reading organization settings
- Department manager managing another department’s document
- Department manager creating organization-wide ACL grants
- Department manager retrieving organization-wide analytics
- Soft-deleted department retaining ACL access
- Cross-tenant path IDs
- Cross-tenant ACL targets
- Cross-tenant conversation/message/feedback IDs
- Role ID from another tenant
- API-key scopes being narrower than the creator’s permissions

The security suite is empty, and these are the highest-risk behaviors.

### 5.4 Document lifecycle (High)

No tests for:

- Extension, size, empty-file, and filename sanitization
- Duplicate content within and across departments
- Concurrent duplicate upload
- Version numbering and current-version update
- ACL replacement, duplicate grants, deny precedence, and organization grants
- Download authorization and MIME handling
- Metadata update authorization
- Delete behavior when Qdrant is down
- MinIO failure during upload/version/delete
- Orphan cleanup and retry
- Soft-deleted document uniqueness behavior

### 5.5 Database and migrations (High)

No test:

- Applies Alembic migrations to an empty database
- Compares migrated schema to ORM metadata
- Runs upgrade/downgrade
- Verifies FKs, checks, indexes, and uniqueness
- Verifies soft-delete query semantics
- Uses real PostgreSQL-specific behavior (`JSONB`, `Uuid`, advisory locks)

SQLite is not a suitable substitute because the models use PostgreSQL-specific types and SQL. Use a disposable PostgreSQL container.

### 5.6 Ingestion and worker (High)

No tests for:

- Celery task registration
- Job creation on upload
- Queue dispatch
- Job state transitions
- Retry/backoff/idempotency
- Dead-letter behavior
- Failure recovery
- Chunk/version consistency
- Embedding/Qdrant upsert batching

### 5.7 Chat and conversations (High)

No tests for:

- 200 `insufficient_evidence` when no documents are indexed
- 503 when indexed documents exist
- Conversation creation across users/tenants
- Message persistence and ordering
- Citation grouping
- Streaming event format
- Missing `chat:ask`/`chat:history_view`
- Message pagination/limits

### 5.8 Upload/Browser/API contracts (Medium)

No tests for:

- Response envelope shape
- Typed OpenAPI response models
- Validation errors
- Pagination bounds
- Query-parameter validation
- HTTP status semantics
- Duplicate document 409 body
- Browser cookie flags and logout
- API-key vs bearer precedence
- Unhandled exception envelope

### 5.9 Deployment and operations (Medium)

No tests for:

- Docker build
- Compose startup
- Migration-before-start
- Worker registration
- Readiness when Redis/MinIO/Celery are down
- Graceful shutdown
- Secret/default rejection
- Production configuration

### 5.10 RAG quality (High for product)

The evaluation suite is empty. Once retrieval exists, tests should cover:

- Recall@k / precision@k on a labeled corpus
- ACL leakage (no unauthorized chunks)
- Citation validity (every citation maps to an authorized chunk)
- Answer groundedness
- Refusal behavior on insufficient evidence
- Prompt-injection resistance
- Latency and cost per query

## 6. Problems with existing tests

### 6.1 Configuration test blesses insecure defaults

`test_settings_have_local_development_defaults` asserts that defaults are usable but does not assert that the secret is not a known placeholder. It effectively permits the insecure default.

**Fix:** add a test that `Settings()` with no secret raises, or that a separate local-only settings mode is explicit. Add a production-settings test that rejects default/weak secrets.

### 6.2 Web tests do not exercise the web bug

`test_web.py` renders the login template and checks route mounting but never calls the home route. The confirmed bug is invisible.

### 6.3 Layering test is bypassable

It only examines calls where the object is named `db` or `session` and only a fixed method denylist. It does not catch `async_sessionmaker`, raw SQL, or API imports in repositories. It is better than nothing but gives false confidence.

### 6.4 Health tests are narrow

They verify liveness/readiness mechanics but not:

- Schema/migration readiness
- Redis/MinIO/Celery readiness
- Readiness timeouts
- Admin health parity
- Probe behavior under dependency latency

### 6.5 Model tests are metadata-only

They assert table names and one reserved column, not constraints, indexes, FK behavior, or migration equivalence.

### 6.6 Qdrant tests are unit-only

They mock the client and verify calls. They do not verify real payload filtering, dimension recreation, or search behavior.

### 6.7 No coverage measurement

No coverage configuration or threshold exists. Even line coverage could reveal that large sections of services are untested.

## 7. Recommended test architecture

### Unit tests

- Pure policy functions (`can_manage_document`, department scope)
- Password hashing/verification
- Token encode/decode
- Settings validation
- Serialization/response models
- Filename/MIME validation
- Pagination bounds
- Score/ACL helper logic

### Repository/integration tests

Use ephemeral PostgreSQL, Redis, Qdrant, and MinIO containers (or contract-tested fakes):

- Tenant-scoped queries
- ACL filter matrix
- Duplicate upload race
- Department deletion cascade
- Conversation/message/citation loading
- API-key lookup and revocation
- Migration application and schema drift
- Qdrant payload filtering and upsert/delete

### API tests

Use `httpx.AsyncClient`/`TestClient` with a real app instance and test database:

- Authentication matrix
- Role/permission matrix
- Tenant/path matrix
- Upload/version/ACL lifecycle
- Chat/conversation/feedback
- Error envelopes and status codes
- Pagination/filtering
- OpenAPI response schemas

### Browser tests

- `/` redirects with/without cookie
- Login success/failure and cookie flags
- Dashboard counts respect ACL
- Documents page pagination
- Logout revokes and clears
- CSRF behavior once added
- HTML escaping

### Security tests

- Forged/expired/wrong-type/wrong-tenant tokens
- Default/weak secret rejection
- API-key scope narrowing and revocation
- Brute-force/rate-limit behavior
- Department/analytics scope
- Organization ACL escalation
- Mass-assignment/unknown fields
- File content spoofing
- Cross-tenant ID enumeration
- Deleted department access
- Audit event presence

### Evaluation tests

- ACL leakage on a labeled corpus
- Citation correctness
- Groundedness and refusal
- Prompt injection
- Retrieval recall and latency budgets
- Cost/token budgets

## 8. Priority regression tests

Add these before or alongside the corresponding fixes:

| Priority | Regression test |
|---|---|
| P0 | `GET /` returns 303 (or login) and never 500 |
| P0 | Startup rejects the known default secret |
| P0 | Employee cannot list departments or department members |
| P0 | Employee cannot read arbitrary organization settings |
| P0 | Department manager cannot manage a document outside their department |
| P0 | Department manager cannot create an organization-wide ACL grant |
| P0 | Department manager analytics excludes other departments |
| P0 | Deleted department no longer grants document access |
| P0 | Cross-tenant role ID is rejected |
| P0 | Fresh database migration produces all tables and starts the app |
| P0 | Delete document removes DB row state, MinIO objects, and Qdrant points (or records a retryable job) |
| P1 | Duplicate upload does not disclose an inaccessible document ID |
| P1 | Chat returns a stable “not configured” error until RAG exists |
| P1 | Conversation endpoints enforce `chat:history_view` |
| P1 | Invalid file content with a valid extension is rejected |
| P1 | Refresh token cannot be reused after rotation |
| P1 | API-key scopes cannot exceed creator permissions |
| P1 | Invitation token is single-use and expires |
| P1 | All mutating endpoints emit audit events |

## 9. Test data and fixtures

Recommended fixtures:

- `org_a`, `org_b`
- `admin_a`, `manager_a`, `employee_a`, `admin_b`
- `dept_a1`, `dept_a2`, `dept_b1`
- documents owned by each department, with ACL grants for user/department/organization and deny
- a soft-deleted department with members and ACL grants
- active/suspended/disabled users and organizations
- valid/expired/revoked access and refresh tokens
- API keys with broad and narrow scopes
- invitation keys valid/expired/revoked
- a labeled RAG corpus with ACLs and known answers

Use factories/builders, not ad hoc dictionary literals, and reset state per test.

## 10. CI test pipeline

Proposed stages:

1. `ruff check .`
2. `python -m compileall -q app alembic`
3. Unit tests
4. Integration tests with services
5. Migration tests from empty
6. Security tests
7. RAG evaluation (once implemented; may be scheduled/nightly)
8. Coverage report with a ratcheting threshold

No CI workflow currently exists. There is no pre-commit config, coverage config, or type-check config. Add them only after the dependency typo/`httpx` issue is fixed.

## 11. Testing scorecard

| Dimension | Score (1–5) | Rationale |
|---|---:|---|
| Unit coverage | 2 | Token/model/config/Qdrant only. |
| Service coverage | 1 | No service tests. |
| API coverage | 1 | Route mounting only. |
| Authorization tests | 1 | None; several confirmed defects would be caught. |
| Tenant isolation tests | 1 | None. |
| Database/migration tests | 1 | None. |
| Worker tests | 1 | No task. |
| Browser tests | 2 | Template/path only; home bug missed. |
| Security tests | 1 | Empty directory. |
| RAG evaluation | 1 | Empty directory. |
| CI enforcement | 1 | No CI. |
| Test maintainability | 3 | Small, readable, deterministic tests. |

## 12. Conclusion

The test suite is a promising start, not a safety net. It validates a few low-level invariants but none of the platform’s security-critical or core user workflows. The fastest path to confidence is to add the P0 regression tests alongside the security fixes, then build a disposable-infrastructure integration suite and a migration test before expanding RAG evaluation.

# 06 — Code Quality Audit

## 1. Summary

The Python code is readable, consistently formatted, and organized around a sensible layered architecture. The main quality problem is not messy code; it is **unfinished code presented alongside finished-looking modules**. Fifty non-package Python files are one-line docstrings, several core modules are empty, and the RAG directory contains 41 files but only 153 lines. This creates a misleading impression of completeness and makes maintenance risky.

**Code quality verdict:** clean foundation with substantial dead/stub surface, duplicated policy logic, and no enforced type or CI quality gate.

## 2. Measured inventory

| Metric | Value |
|---|---:|
| Python files under `app/` | 176 |
| Total lines under `app/` | 5,860 |
| One-line Python files under `app/` | 83 |
| Non-`__init__` one-line files | 50 |
| Lines under `app/rag/` | 153 across 41 files |
| Lines under `app/integrations/` | 166 across 12 files |
| Largest service | `document_service.py`, 413 lines |
| Largest auth module | `auth_service.py`, 369 lines |
| Largest schema module | `requests.py`, 132 lines |
| Empty/one-line core modules | `logging.py`, `middleware.py`, `permissions.py` |
| Empty/one-line database module | `init_db.py` |
| Empty/one-line worker task | `ingestion_worker.py` |

The one-line files are not all defects: package `__init__.py` files are expected to be small. The concern is the 50 non-package modules that look like implementations but contain only a docstring.

## 3. Strengths

1. **Consistent formatting.** Ruff configuration is present, line length is 88, and rules E/F/I/UP/B are selected.
2. **Readable naming.** Services, repositories, routes, and models use predictable names.
3. **Thin routes.** Route handlers generally validate input and delegate to services.
4. **Clear response helpers.** Success/error envelopes are centralized.
5. **Explicit tenant predicates.** Repositories consistently accept `organization_id` and apply it.
6. **No SQL string interpolation** for user-controlled values.
7. **No debug leftovers.** No `print`, `breakpoint`, `pdb`, `eval`, or `exec` found.
8. **No suppression comments.** No `type: ignore` or `noqa` found.
9. **Docstrings are useful.** Most public functions have concise docstrings.
10. **Architecture test exists.** `test_layering.py` is a good idea and catches obvious violations.
11. **Small modules.** Outside the two largest services, most modules are focused.
12. **UUIDv7 helper** is compact and correct in intent.

## 4. Major code-quality issues

### 4.1 Stub explosion and misleading surface (High)

The following modules are one-line docstrings or empty:

**RAG (41 files, 153 lines):**
- `app/rag/pipeline.py`, `app/rag/config.py`
- `chunkers/fixed_chunker.py`, `semantic_chunker.py`
- `cleaners/text_cleaner.py`
- `embeddings/embedding_service.py` and all providers
- all extractors (`pdf`, `docx`, `xlsx`, `txt`, `html`, `ocr`)
- all generators/providers
- all prompts
- all rerankers/retrievers

**Services:**
- `citation_service.py`, `retrieval_service.py`, `reranking_service.py`

**Schemas:**
- `analytics.py`, `auth.py`, `chat.py`, `citation.py`, `conversation.py`, `department.py`, `document.py`, `feedback.py`, `ingestion.py`, `organization.py`, `user.py`

**Integrations/workers/core:**
- `integrations/redis/client.py`
- `integrations/storage/s3_storage.py`
- `integrations/llm/factory.py`
- `workers/ingestion_worker.py`
- `core/logging.py`, `core/middleware.py`, `core/permissions.py`
- `database/init_db.py`
- `middleware/tenant_context.py`
- `utils/datetime.py`, `utils/pagination.py`

**Impact:**

- Readers cannot tell implemented behavior from planned behavior.
- Imports can succeed while functionality silently does nothing.
- Tests may import a module and assume it works.
- Documentation generated from the tree overstates maturity.
- Onboarding time increases because every empty module must be investigated.

**Remediation:**

- Either delete unused stubs or mark them explicitly with `NotImplementedError` and a tracking reference.
- Do not ship empty modules that appear importable.
- Add a repository check that fails if a non-package module is only a docstring.
- Consolidate the RAG package to the modules needed for the first vertical slice.

### 4.2 Duplicated authorization policy (High)

Authorization is implemented ad hoc in multiple services:

- `_can_manage` in `document_service.py`
- `_can_manage` in `department_service.py`
- `_ensure_same_tenant` in `department_service.py`, `organization_service.py`, and `user_service.py`
- Inline checks in `auth_service`, `feedback_service`, `analytics_service`, `admin_service`, `ingestion_service`
- `require_permissions` in `app/api/dependencies.py` is defined but unused

This has already produced divergent behavior. Document management ignores department scope; analytics accepts a department permission but queries organization data; department reads have no permission check.

**Remediation:**

- Create an authorization module with small pure functions:
  - `require_tenant(principal, org_id)`
  - `require_permission(principal, *permissions)`
  - `require_department_scope(principal, department_id)`
  - `can_manage_document(principal, document)`
- Use route-level dependencies for coarse checks and service-level policy for resource-specific checks.
- Add table-driven tests for role × resource × action.

### 4.3 Generic ORM serialization (Medium/High)

`serialize_model` returns every table column except `password_hash` and `key_hash`. It is convenient but couples API contracts to database columns and risks future leaks (for example, a new `secret` or `token` column). Most response schemas are empty, so OpenAPI does not describe the output.

**Remediation:**

- Define explicit Pydantic response models per endpoint.
- Select only fields needed by the caller.
- Keep a separate internal serializer for admin/audit needs.
- Add a test that no response contains known sensitive field names.

### 4.4 Consolidated request schema file and empty domain schemas (Medium)

All request bodies live in `app/schemas/requests.py`, while `app/schemas/<domain>.py` files are stubs. This is not inherently wrong, but it contradicts the package structure and concentrates unrelated models in one file.

**Remediation:** move request/response models into their domain modules and keep `requests.py` as a temporary re-export if needed. Use `extra="forbid"` for security-sensitive inputs.

### 4.5 Premature package structure (Medium)

`app/rag/` has a directory tree for every conceivable component, but no implementation. `app/integrations/` similarly contains adapters for providers that do not exist. This is speculative generality.

**Remediation:** build one end-to-end path first: extract → clean → chunk → embed → store → retrieve → cite → generate. Add modules only as each stage is implemented.

### 4.6 Module-global state and weak testability (Medium)

- `settings` is a module-level cached singleton.
- `engine` and session factory are created at import.
- `app` is a module-level FastAPI instance.
- Auth imports `settings` directly.
- Storage creates `MinioStorage()` inside service functions.
- Redis is accessed through `request.app.state`, but auth functions receive it as a parameter inconsistently.

**Impact:** tests must monkeypatch module attributes; multiple environments in one process are difficult; worker and API configuration cannot be independently composed.

**Remediation:** introduce an application factory and dependency providers, or at minimum pass settings/clients explicitly into service functions and test them with fakes.

### 4.7 Function-local imports (Low/Medium)

Examples: `app/services/auth_service.py:186`, `app/services/document_service.py:83`, `app/repositories/conversation_repository.py:60`, `app/repositories/auth_repository.py:24-26`, and repeated `from datetime import UTC, datetime` imports.

Function-local imports avoid cycles but hide dependencies and add noise. They also make it harder to see layering violations.

**Remediation:** break cycles by moving shared types to a lower-level module, then use module-level imports consistently.

### 4.8 Weak typing and no type gate (Medium)

- Many repositories return `Any`.
- `one_or_none`/`all`/`rows`/`scalar` are untyped.
- `file` parameters and some service returns are untyped.
- Response functions return bare `dict`.
- `model_dump` dictionaries are applied with `setattr` without key validation.
- No mypy/pyright configuration or CI check.

**Remediation:** add a type checker in non-strict mode first, type repository generics, and use typed DTOs. Enforce `ruff` and type checks in CI.

### 4.9 Inconsistent transaction ownership (Medium)

Repositories both build queries and commit. Services sometimes call `repository.commit()` and sometimes repository methods commit internally (`create`, `save`, `create_invitation`, `persist_initial_upload`, `replace_permissions`). This makes transaction boundaries hard to reason about.

**Remediation:** decide whether repositories are transaction-free query/unit-of-work helpers or own commits. Prefer a service-owned unit of work. Avoid hidden commits inside query methods.

### 4.10 Broad exception handling (Medium)

- `main.py` catches `Exception` for readiness and admin health; acceptable for health aggregation, but logs with `logger.exception` and hides types.
- `document_service.delete_document` catches `Exception` around Qdrant cleanup; appropriate to avoid crashing, but the resulting state is inconsistent.
- Redis failures are sometimes caught as `RedisError` only; other network exceptions may escape as 500.

**Remediation:** catch specific exception types, map them to stable API errors, and preserve consistent state. Use a small error taxonomy per integration.

### 4.11 No structured logging configuration (Medium)

`logging.getLogger` is used, but there is no formatter, handler, level, correlation-ID injection, or redaction. `logger.exception` includes tenant IDs and storage keys. Request ID is generated but not attached to logs.

**Remediation:** configure structured JSON logging at startup, inject request/tenant/user IDs, redact secrets, and add security-event logs.

### 4.12 Dependency and configuration hygiene (Medium)

- `httpx2>=2.0,<3` is almost certainly a typo for `httpx`; tests use `fastapi.testclient`, which requires `httpx`.
- `boto3`, `beautifulsoup4`, `PyMuPDF`, `python-docx`, and `openpyxl` are declared but unused by current code.
- AI dependencies are an optional extra, but the Dockerfile installs base only.
- Root and application `requirements.txt` mirror each other, while `pyproject.toml` is canonical; drift is likely.
- No lock file.
- No CI, pre-commit, or dependency audit.

**Remediation:** fix dependency names, remove unused direct dependencies or document their planned stage, add a lock file, and make CI install the exact deployment set.

### 4.13 Documentation drift and unsafe generator (Medium)

`README.md` says authentication/business modules do not exist in places, while they do. `docs/18`, `docs/19`, and other design docs describe phases that have moved on. `generate_docs.py` hardcodes a Windows path and rewrites all documentation.

**Remediation:** make code-derived docs explicit, update README to current state, remove or fix the generator, and add a docs check for stale claims.

### 4.14 Unused schema classes and aliases (Low)

`ORMResponse`, `TokenPair`, `UploadAccepted`, and `TimestampFilter` are defined but unused. `app/api/v1/common.py` re-exports `serialize_model` from the service layer, blurring boundaries.

**Remediation:** remove unused classes or wire them into typed responses.

### 4.15 Architecture test is easy to bypass (Low/Medium)

`test_layering.py`:

- Only inspects calls where the receiver is literally named `db` or `session`.
- Only checks a fixed method-name denylist.
- Does not detect `async_sessionmaker` use, raw SQL construction, or repository imports in the API.
- Does not check that services avoid models or integrations.

It is useful as a smoke test but not a robust architecture guarantee.

**Remediation:** combine AST checks with import-graph rules (for example, `import-linter`) and review exceptions.

## 5. File-by-file quality notes

| File | Observation |
|---|---|
| `app/services/document_service.py` | Largest service; mixes upload, ACL, storage, Qdrant, and serialization. Split into `document_upload_service`, `document_acl_service`, and `document_query_service`. |
| `app/services/auth_service.py` | Handles registration, login, refresh, logout, API keys, and principal resolution. Cohesive but long; extract token/API-key concerns. |
| `app/services/department_service.py` | Simple CRUD; missing permission policy and cascade behavior. |
| `app/services/analytics_service.py` | Good size; incorrect scope logic. |
| `app/services/chat_service.py` | Honest placeholder but conflates “no evidence” with “not configured.” |
| `app/services/common.py` | Useful serialization/pagination helper; generic serializer is risky for API contracts. |
| `app/repositories/base.py` | Convenient but broad; `get` allows tenant bypass if misused. |
| `app/repositories/auth_repository.py` | Multiple sequential queries; mixes identity and API-key persistence. |
| `app/repositories/document_repository.py` | ACL logic is centralized and readable; index and tenant-consistency gaps. |
| `app/models/` | Clean declarative style; schema gaps are documented in `03-database-analysis.md`. |
| `app/api/v1/` | Consistently thin; response models absent. |
| `app/core/config.py` | Clear grouping; insecure defaults and no validation. |
| `app/auth/token.py` | Compact and understandable; missing standard claims/key rotation. |
| `app/web.py` | Minimal but broken home route; no CSRF/refresh/UI features. |
| `app/main.py` | Clear lifespan; global app and weak readiness. |
| `app/tests/` | Small but meaningful architecture/token/model tests. |
| `app/rag/` | Not an implementation; a directory sketch. |

## 6. Complexity and duplication hotspots

| Area | Issue |
|---|---|
| Tenant assertion | Three private copies of `_ensure_same_tenant` |
| Management checks | Two unrelated `_can_manage` functions with different semantics |
| Error mapping | Services raise `HTTPException` directly, mixing transport and domain |
| Serialization | `serialize_model` used for users, documents, conversations, ACLs, jobs, feedback |
| Datetime imports | Repeated function-local imports |
| Pagination | Two validation locations (repository and browser service) |
| Status literals | Repeated string literals across models, schemas, services |
| API paths | Hardcoded organization/document nesting with inconsistent conventions |

## 7. Code-quality recommendations

### P0

1. Delete or explicitly mark all stubs; do not ship importable empty modules.
2. Consolidate authorization into one tested policy module.
3. Fix the `cookies.et` bug and add a browser test.
4. Fix `httpx2` and verify the dev dependency set.
5. Add a CI job that runs `ruff`, tests, and `compileall`.

### P1

6. Add typed response models and remove generic ORM serialization from public APIs.
7. Move request schemas into domain modules and validate unknown fields.
8. Add an application factory and injectable clients.
9. Choose one transaction ownership model.
10. Split `document_service` and `auth_service`.
11. Add structured logging with redaction.
12. Type repository interfaces and add a gradual type check.

### P2

13. Build one RAG vertical slice and remove speculative modules until needed.
14. Add import-graph architecture checks.
15. Add deprecation and migration notes to docs.
16. Remove unused dependencies/schemas.
17. Add docstring style and public-API documentation checks.

## 8. Code quality scorecard

| Dimension | Score (1–5) | Rationale |
|---|---:|---|
| Readability | 4 | Clear names, small functions, useful docstrings. |
| Organization | 3 | Good layering; premature empty packages. |
| Completeness | 1 | Core RAG/ingestion path absent; many stubs. |
| Duplication | 2 | Authorization/tenant checks repeated. |
| Type safety | 2 | Annotations exist but are loose; no type gate. |
| Error handling | 3 | Central API handlers are good; integration/state errors weak. |
| Testability | 2 | Global state and direct imports hinder substitution. |
| Tooling | 2 | Ruff/pytest config exists; no CI, lock file, or type check. |
| Documentation accuracy | 2 | Design docs and README overstate implementation. |
| Maintainability | 3 | Manageable size, but hidden stubs and policy drift raise risk. |

## 9. Conclusion

The code does not need a rewrite. It needs **truthful boundaries and enforced policy**. Removing or explicitly marking stubs, centralizing authorization, adding typed API contracts, and establishing CI will produce a disproportionate quality improvement. Until then, the codebase’s clean appearance is less reliable than it seems.

# 01 — Project Overview

**Audit date:** 2026-11-10  
**Audit type:** Static, read-only code and configuration review  
**Product:** Enterprise RAG  
**Repository root:** `/mnt/f/project/genAI-projects`  
**Application root:** `/mnt/f/project/genAI-projects/enterprise-rag`

## 1. Purpose of this document

This document establishes the scope, inventory, maturity baseline, and terminology used by the other audit documents. It describes what exists in the repository, not what the design documents say should exist.

## 2. Scope and method

### In scope

- Python application under `enterprise-rag/app/`
- API routes under `app/api/`
- Browser routes and Jinja templates under `app/web.py` and `app/templates/`
- Services, repositories, ORM models, schemas, auth, middleware, integrations, workers, and RAG scaffolding
- Tests under `app/tests/` and `enterprise-rag/tests/`
- Build, dependency, environment, container, and deployment configuration
- Existing design documents under `enterprise-rag/docs/` used as a comparison baseline

### Excluded

- Runtime behavior requiring installed dependencies or live PostgreSQL, Qdrant, Redis, or MinIO
- The Windows `env/` virtual environment
- Generated caches, egg-info, `.git`, and compiled bytecode
- The standalone prototype CLIs at the git root (`qdrant_checking.py`, `rag_query.py`)
- Security exploitation, penetration testing, and load testing

### Method

1. Inventory files and lines of code.
2. Read routes, services, repositories, models, configuration, tests, and deployment files.
3. Trace authentication, authorization, tenant isolation, upload, chat, and browser flows.
4. Compare implementation claims in `docs/*.md` with code and tests.
5. Run only non-mutating static validation.
6. Assign severities using the scale in Section 8.

## 3. Product summary

Enterprise RAG is intended to be a multi-tenant document knowledge platform. The designed capabilities include:

- Organization, user, role, invitation, and department management
- PDF/DOCX/XLSX/TXT/HTML upload and versioning
- MinIO object storage and Qdrant vector search
- PostgreSQL metadata, Redis caching/revocation, and Celery background ingestion
- Retrieval, reranking, grounded generation, and citations
- Conversations, feedback, analytics, audit logs, and a small server-rendered UI

The implemented application is best described as an **early-stage modular monolith with a working authentication/CRUD foundation and substantial RAG scaffolding**. The retrieval and generation path is not implemented.

## 4. Actual technology stack

| Layer | Technology | Evidence |
|---|---|---|
| Language | Python 3.11+ declared; interpreter used for validation was 3.14 | `pyproject.toml:11`; local runtime |
| API | FastAPI, Starlette | `app/main.py:7-12` |
| Browser UI | Jinja2 templates, minimal inline HTML/CSS | `app/web.py:9-10`; `app/templates/` |
| ORM | SQLAlchemy 2.x async | `app/database/session.py`; `app/models/` |
| Database | PostgreSQL via `asyncpg` | `pyproject.toml`; `app/core/config.py:50-58` |
| Vector DB | Qdrant via `qdrant-client` | `app/integrations/qdrant/client.py` |
| Cache / revocation | Redis via `redis.asyncio` | `app/main.py:31-33`; `app/services/auth_service.py` |
| Queue | Celery with Redis broker/backend | `app/workers/celery_app.py` |
| Object storage | MinIO S3-compatible API | `app/integrations/storage/minio_storage.py` |
| Auth | Hand-rolled HS256 JWT using stdlib `hmac` | `app/auth/token.py` |
| Password hashing | PBKDF2-HMAC-SHA256, 310,000 iterations | `app/core/security.py:11-28` |
| Validation | Pydantic v2 | `app/schemas/requests.py` |
| Testing | pytest, pytest-asyncio, httpx | `pyproject.toml:35-48` |
| Linting | Ruff | `pyproject.toml:58-65` |

## 5. Repository layout

```text
enterprise-rag/
├── app/
│   ├── api/                 # Versioned API routes, common response helpers, dependencies
│   ├── auth/                # HS256 JWT signing and verification
│   ├── core/                # Settings, identity, security, exceptions, constants
│   ├── database/            # Declarative base, engine/session factory
│   ├── integrations/        # Qdrant, MinIO, Redis, and LLM adapters
│   ├── middleware/          # Request ID and tenant context
│   ├── models/              # 21 SQLAlchemy tables
│   ├── rag/                 # Mostly empty extractor/chunker/retriever/generator scaffolding
│   ├── repositories/        # SQLAlchemy query layer
│   ├── schemas/             # Request models plus mostly empty response modules
│   ├── services/            # Business logic and authorization checks
│   ├── templates/           # Login, dashboard, documents, conversations
│   ├── tests/               # Unit and architecture tests
│   ├── utils/               # File validation and helpers
│   ├── workers/             # Celery app and stub ingestion task
│   ├── main.py              # Application factory-by-module, startup checks, health
│   └── web.py               # Server-rendered browser routes
├── alembic/                 # Configured but has no migration revisions
├── docs/                    # Existing design/spec set and this audit
├── tests/                   # Smoke tests
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## 6. Maturity assessment

| Capability | Status | Assessment |
|---|---|---|
| Settings and startup | Partial | Typed setting groups and startup checks exist; insecure defaults and missing migration/bootstrap are material gaps. |
| Authentication | Partial | JWT login, refresh, logout, invitation acceptance, API keys, and Redis revocation exist. No password reset, MFA, login throttling, or super-admin bootstrap. |
| Authorization | Partial | Default roles and server-side ACL filters exist, but several endpoints have missing or incorrectly scoped checks. |
| Tenant isolation | Partial | Most queries are server-scoped by the principal's organization. Cross-tenant data-integrity constraints are incomplete. |
| Organization/user/department CRUD | Functional with gaps | Basic flows exist; provisioning of new organizations and role changes are incomplete. |
| Document upload/version/ACL | Partial | Upload, duplicate detection, versions, and ACL replacement exist; storage and vector cleanup are not transactional, and MIME/content validation is weak. |
| Ingestion | Not implemented | Jobs are created and exposed but no worker task is registered; status remains `queued`. |
| Retrieval/reranking/generation | Not implemented | Services and RAG modules are stubs. Chat returns `insufficient_evidence` or HTTP 503. |
| Conversations | Partial | CRUD and persistence exist; no real answers, message pagination, export, or delete. |
| Feedback | Minimal | Create/read only; no review workflow despite docstrings. |
| Analytics | Minimal | Document/job counts work; usage metrics remain zero because no usage records are written. |
| Audit logging | Not implemented | Model and repository exist; no service or API writes or reads audit events. |
| Browser UI | Broken/limited | Home route has a confirmed cookie API bug; UI is read-only and has no upload/chat controls. |
| Observability | Minimal | Request IDs and health endpoints exist; no structured logs, metrics, traces, or error tracking. |
| Tests | Minimal | 16 test functions in 7 files; integration, security, and evaluation suites are empty. |
| Deployment | Development-only | Compose works as a local topology; no migrations, TLS, worker task, production hardening, or CI. |

## 7. Key inventory numbers

| Metric | Value | Notes |
|---|---:|---|
| Python files under `app/` | 176 | Includes tests and stubs |
| One-line Python files under `app/` | 83 | Includes package `__init__.py` files |
| Non-`__init__` one-line files | 50 | Mostly RAG, schema, and integration stubs |
| Lines under `app/api/` | 1,011 | 18 files |
| Lines under `app/services/` | 1,607 | 16 files |
| Lines under `app/repositories/` | 1,021 | 12 files |
| Lines under `app/models/` | 792 | 23 files, 21 tables |
| Lines under `app/rag/` | 153 | 41 files |
| Lines under `app/integrations/` | 166 | 12 files |
| HTTP route decorators | 53 | 46 API + 7 browser, excluding `/health` and `/ready` |
| SQLAlchemy tables | 21 | Enforced by `app/tests/unit/test_models.py` |
| Alembic revision files | 0 | `alembic/versions/` is empty apart from package/placeholder files |
| Test functions | 16 | Across 7 test files |

## 8. Severity scale

| Severity | Meaning |
|---|---|
| Critical | Exploitable security issue, authentication bypass, or data exposure with immediate production impact. |
| High | Broken core workflow, cross-tenant/privilege issue, or production blocker requiring urgent correction. |
| Medium | Material correctness, resilience, security-hardening, or maintainability issue. |
| Low | Limited-impact defect, inconsistency, documentation drift, or polish item. |
| Info | Observation or future improvement with no immediate risk. |

## 9. Confirmed high-level findings

1. **Critical:** The default application secret is a known placeholder, and `.env.example` does not require an override.
2. **High:** The browser home route calls a non-existent cookie method and will raise an exception.
3. **High:** Department managers can manage documents outside their department and can create organization-wide ACL grants.
4. **High:** Department-scoped analytics permissions expose organization-wide analytics.
5. **High:** Department and organization read endpoints lack consistent permission enforcement.
6. **High:** No database migrations exist, and startup readiness can report ready without a usable schema.
7. **High:** Ingestion and RAG are stubs, so the core product workflow cannot succeed.
8. **High:** No code path bootstraps a `super_admin`, making platform administration unreachable.
9. **High:** Soft-deleting a department does not revoke document access granted through that department.
10. **High:** Test coverage, CI, observability, and production deployment controls are insufficient for release.

Detailed evidence and remediation are in documents 02–11.

## 10. How to read this audit

- **Documents 02–04** describe the actual architecture, database, and API surface.
- **Documents 05–09** assess security, code quality, performance, testing, and deployment.
- **Document 10** provides a sequenced remediation roadmap.
- **Document 11** is the executive decision summary and top-10 risk list.

## 11. Audit limitations

- Dependencies are not installed in the audit environment. `pytest` stops during collection because `fastapi`, `qdrant_client`, and other packages are unavailable.
- No live infrastructure was used. Findings about external-service behavior are based on static code inspection.
- No dynamic exploitation, fuzzing, or performance measurement was performed.
- Existing `docs/*.md` are design/specification material and sometimes describe target behavior rather than current behavior.
- The working tree already contained extensive modifications before this audit. No application source was changed by the auditor.
- Severity and effort estimates are professional judgments, not measured production incident data.

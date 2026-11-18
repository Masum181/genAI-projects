# 04 — API Analysis

## 1. Summary

The API is a clean, conventional FastAPI surface with 46 versioned endpoints, a consistent success/error envelope, and server-resolved tenancy. It is not contract-complete for the advertised product: several endpoint families are placeholders, authorization is inconsistent, and some response/status semantics are misleading.

**API verdict:** usable CRUD/auth API foundation; not ready for external consumers or production.

## 2. API conventions

### 2.1 Mounting and prefixes

- API prefix: `APP_API_V1_PREFIX`, default `/api/v1` (`app/core/config.py:20-24`).
- Browser routes are mounted separately at `/`, `/login`, `/ui/*`.
- Operational endpoints are not under `/api/v1`: `/health`, `/ready`.

### 2.2 Authentication

`get_current_principal` resolves identity from:

1. `X-API-Key`
2. `Authorization: Bearer <access JWT>`
3. `access_token` browser cookie

All protected API routes use this dependency. Missing or invalid credentials produce 401. API keys are scope-limited; browser tokens and API keys both resolve to a `Principal` built from server-side membership data.

Evidence: `app/api/dependencies.py:84-125`, `app/services/auth_service.py:298-354`.

### 2.3 Success envelope

```json
{
  "success": true,
  "request_id": "UUID",
  "data": {},
  "error": null
}
```

### 2.4 Error envelope

```json
{
  "success": false,
  "request_id": "UUID",
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "Document not found",
    "details": null
  }
}
```

Handled: custom 404/403/409, `HTTPException`, and Pydantic validation errors. Unhandled exceptions use FastAPI’s default 500 response, which does not follow this envelope. `/health` and `/ready` intentionally return plain JSON.

### 2.5 Pagination

Page-based pagination uses `page` and `page_size`; `page_size` is capped at 100 in the repository and validated again in the browser document list. There is no cursor pagination, sorting control, or stable secondary sort key.

## 3. Endpoint inventory

Counts: **46 API endpoints**, 7 browser routes, 2 operational endpoints.

### 3.1 Authentication — 9

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Public | Only succeeds when zero organizations exist |
| POST | `/api/v1/auth/login` | Public | Active user + active organization + active membership |
| POST | `/api/v1/auth/refresh` | Refresh JWT | Active user + active membership; token revocation checked |
| POST | `/api/v1/auth/accept-invite` | Invitation token | Valid, unrevoked, unexpired invitation key |
| POST | `/api/v1/auth/logout` | Any principal | Revokes supplied access, refresh, and/or API key |
| POST | `/api/v1/auth/api-keys` | Any principal | Requested scopes must be a subset of current permissions |
| GET | `/api/v1/auth/api-keys` | Any principal | Own keys; admins see all keys in the organization |
| DELETE | `/api/v1/auth/api-keys/{key_id}` | Any principal | Own key; admins can revoke any key in organization |
| GET | `/api/v1/auth/me` | Any principal | Returns identity, roles, permissions |

### 3.2 Organizations — 4

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| GET | `/api/v1/organizations` | Any principal | Own organization; super-admin can list all |
| POST | `/api/v1/organizations` | Any principal | Super-admin only |
| GET | `/api/v1/organizations/{organization_id}` | Any principal | Same tenant or super-admin; **no permission check** |
| PATCH | `/api/v1/organizations/{organization_id}` | Any principal | Organization admin |

### 3.3 Users — 5

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| GET | `/api/v1/users/me` | Any principal | Self |
| GET | `/api/v1/organizations/{organization_id}/users` | Any principal | Admin, `user:manage_org`, or `organization:read_self` |
| POST | `/api/v1/organizations/{organization_id}/users/invite` | Any principal | Admin or `user:invite`; only admins may invite admins |
| PATCH | `/api/v1/organizations/{organization_id}/users/{user_id}` | Any principal | Organization admin only |
| DELETE | `/api/v1/organizations/{organization_id}/users/{user_id}` | Any principal | Organization admin only; cannot self-delete |

### 3.4 Departments — 5

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| GET | `/api/v1/organizations/{organization_id}/departments` | Any principal | Same tenant; **no permission check** |
| POST | `/api/v1/organizations/{organization_id}/departments` | Any principal | Admin or `department:manage_org` |
| PATCH | `/api/v1/organizations/{organization_id}/departments/{department_id}` | Any principal | Admin or `department:manage_org` |
| DELETE | `/api/v1/organizations/{organization_id}/departments/{department_id}` | Any principal | Admin or `department:manage_org` |
| GET | `/api/v1/organizations/{organization_id}/departments/{department_id}/members` | Any principal | Same tenant; **no permission check** |

### 3.5 Documents — 9

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| GET | `/api/v1/documents` | Any principal | ACL-filtered list |
| POST | `/api/v1/documents/upload` | Any principal | Admin or `document:upload` |
| POST | `/api/v1/documents/{document_id}/versions` | Any principal | Authorized document and (owner or any manager) |
| GET | `/api/v1/documents/{document_id}` | Any principal | Authorized document |
| GET | `/api/v1/documents/{document_id}/download` | Any principal | Authorized document |
| PATCH | `/api/v1/documents/{document_id}` | Any principal | Authorized document and (owner or any manager) |
| DELETE | `/api/v1/documents/{document_id}` | Any principal | Authorized document and any manager |
| GET | `/api/v1/documents/{document_id}/permissions` | Any principal | Authorized document and any manager |
| PUT | `/api/v1/documents/{document_id}/permissions` | Any principal | Authorized document and any manager |

“Any manager” is a confirmed authorization defect: `document:manage_department` is not scoped to the document’s department. See `05-security-audit.md`.

### 3.6 Ingestion — 2

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| GET | `/api/v1/ingestion-jobs/{job_id}` | Any principal | Job in organization; document must be authorized |
| GET | `/api/v1/documents/{document_id}/ingestion-jobs` | Any principal | Authorized document |

Both endpoints expose job state only. No endpoint starts, retries, cancels, or streams ingestion. Upload is the only producer, and no consumer exists.

### 3.7 Chat — 2

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| POST | `/api/v1/chat` | Any principal | Admin or `chat:ask` |
| POST | `/api/v1/chat/stream` | Any principal | Admin or `chat:ask` |

Current behavior:

- `POST /chat` returns HTTP 200 with a persisted `insufficient_evidence` answer when zero indexed documents exist.
- It returns HTTP 503 when any indexed document exists.
- `stream` is accepted in `ChatRequest` but ignored; `/chat` always returns JSON.
- `/chat/stream` always emits one `token` event and one `end` event, regardless of evidence.
- No citations are ever returned.

### 3.8 Conversations — 4

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| GET | `/api/v1/conversations` | Any principal | Own conversations |
| POST | `/api/v1/conversations` | Any principal | Creates owned conversation; **no `chat:history_view` check** |
| GET | `/api/v1/conversations/{conversation_id}` | Any principal | Own conversation; **no `chat:history_view` check** |
| PATCH | `/api/v1/conversations/{conversation_id}` | Any principal | Own conversation; **no permission check** |

There is no conversation delete endpoint, no message pagination, no export, and no share/collaboration model.

### 3.9 Feedback — 2

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| POST | `/api/v1/feedback` | Any principal | Admin or `feedback:create`; owned conversation and assistant message |
| GET | `/api/v1/feedback/{feedback_id}` | Any principal | Own feedback only |

No review, triage, aggregation, or admin listing endpoint exists.

### 3.10 Analytics — 2

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| GET | `/api/v1/admin/analytics/usage` | Any principal | Admin, `analytics:read_org`, or `analytics:read_department` |
| GET | `/api/v1/admin/analytics/documents` | Any principal | Admin, `analytics:read_org`, or `analytics:read_department` |

Both endpoints return **organization-wide** data. Department-scoped permission is not scoped to a department. The path is also misleading for a department manager, because it is under `/admin`.

### 3.11 Administration — 2

| Method | Path | Auth | Effective authorization |
|---|---|---|---|
| GET | `/api/v1/admin/health` | Any principal | Admin or `platform:read_all`; checks PostgreSQL, Qdrant, Redis |
| GET | `/api/v1/admin/metrics` | Any principal | Admin or `platform:read_all`; own organization unless super-admin |

Admin health omits MinIO and Celery/broker health. Metrics are org counts only.

## 4. Browser routes

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/` | Optional | **Calls `request.cookies.et(...)`; raises `AttributeError`** |
| GET | `/login` | Public | Renders login page |
| POST | `/login` | Public | Sets `access_token` HttpOnly SameSite=Strict cookie |
| GET | `/ui/` | Cookie/bearer | Dashboard with document/conversation counts |
| GET | `/ui/documents` | Cookie/bearer | Read-only paginated document list |
| GET | `/ui/conversations` | Cookie/bearer | Read-only recent conversation list |
| POST | `/ui/logout` | Cookie/bearer | Revokes browser access token, clears cookie |

The UI has no upload, chat, ACL, department, user, or settings controls. There is no CSRF token and no refresh-cookie flow; sessions end after the access-token lifetime.

## 5. Confirmed API defects

### 5.1 `cookies.et` typo (High)

`app/web.py:22` calls `request.cookies.et("access_token")`. `Cookies` has no `et` attribute; this raises before rendering the home page. The regression test suite does not exercise `/`.

### 5.2 Department managers are over-authorized (High)

`_can_manage` in `app/services/document_service.py:56-60` returns true for either organization or department management permission. It does not verify the document’s department or the manager’s department membership/role. Combined with ACL read access, a manager can version, edit, delete, and replace ACLs on any document they can read—including documents outside their department.

### 5.3 Organization-wide ACL escalation (High)

`replace_document_permissions` accepts `grant_type: "organization"` and sets `target_id = None` without requiring an organization-admin permission. A department manager can grant `read`, `write`, or `admin` to every user in the organization on any document they can manage. The access filter treats organization grants as matching every user.

Evidence: `app/services/document_service.py:361-406`, `app/repositories/document_repository.py:178-181`.

### 5.4 Analytics scope leak (High)

`_authorize_analytics` accepts `analytics:read_department`, but both analytics queries use only `principal.organization_id`. Any department manager sees organization-wide usage, document, and job metrics.

Evidence: `app/services/analytics_service.py:12-17`, `app/services/analytics_service.py:20-56`.

### 5.5 Missing permission checks on department/organization reads (High)

- Any authenticated employee can list all departments.
- Any authenticated employee can list members of any department in the organization.
- Any authenticated employee can read organization name, status, and settings.

Tenant scoping prevents cross-organization access, but the role model’s read permissions are not enforced. Organization `settings` is an arbitrary JSON object and may contain sensitive configuration.

Evidence: `app/services/department_service.py:26-42`, `app/services/department_service.py:130-153`, `app/services/organization_service.py:49-58`.

### 5.6 Chat history permissions are ignored (Medium)

`conversations` endpoints check ownership but never `chat:history_view`. A role with that permission removed can still create, list, read, and update conversations. Since ownership is enforced, this is not a cross-user leak, but it makes permission revocation ineffective.

### 5.7 Chat contract is misleading (High functional)

`ChatRequest.stream` is ignored; the non-streaming endpoint always returns `status: insufficient_evidence` with 200; the streaming endpoint emits a fake single token; with indexed data, both fail with 503. Clients cannot distinguish “no evidence” from “feature unavailable” via a stable error contract.

### 5.8 Upload duplicate response leaks document IDs (Medium)

`upload_document` returns `"Duplicate document content; existing document is {duplicate_id}"` (409). A user with upload permission can probe file content and learn document IDs from departments they cannot see. The existence of a document is itself information leakage.

Evidence: `app/services/document_service.py:139-144`.

### 5.9 API paths drift from design docs (Low/Medium)

Examples:

- Upload is `/documents/upload`, not organization-nested.
- Ingestion is `/ingestion-jobs/{id}`, not the documented ingestion namespace.
- Analytics is under `/admin/analytics` despite department-scoped access.
- Conversation creation takes `title` as a query parameter rather than a JSON body.
- Feedback has no organization nesting.
- Browser UI paths use `/ui/` with no trailing-route parity to the docs.

This complicates client generation, versioning, and documentation.

### 5.10 Error contract is incomplete (Medium)

Unhandled exceptions do not use the documented envelope. Rate-limit responses do not exist. Some service-raised `HTTPException`s use messages that reveal internal IDs. There is no error code for 429, 500, or 503 in the mapping, so they become generic `HTTP_ERROR`.

### 5.11 `require_permissions` is dead code (Medium maintainability/security)

The dependency exists at `app/api/dependencies.py:25-41` but is not used by any route. Authorization is duplicated in services, and the duplication has already drifted.

### 5.12 No request/response schemas for most responses (Medium)

Response bodies are ad hoc dictionaries built from ORM serialization. The `schemas/` modules for auth, chat, citation, conversation, department, document, feedback, ingestion, organization, and user are one-line stubs. OpenAPI therefore lacks accurate response models, and destructive schema changes are not caught at development time.

### 5.13 OpenAPI exposure and docs (Low/Medium)

FastAPI docs (`/docs`, `/redoc`, `/openapi.json`) are enabled by default in all environments. There is no configuration to disable them in production. The spec also omits most response schemas, making external client generation weak.

### 5.14 Pagination and filtering (Medium)

- No maximum `page` or offset bound.
- No cursor pagination for large datasets.
- No sorting controls; all endpoints use fixed sort.
- `status_filter` is an unvalidated string; invalid values return empty results rather than 422.
- Conversation history is not paginated.
- Analytics has no pagination because it is aggregate.

### 5.15 HTTP semantics (Low/Medium)

- Upload/version return 202, but no worker consumes the job.
- Delete returns 200 with `deleted: true`; 204 is more conventional but not required.
- Duplicate upload returns 409, appropriate.
- Chat returns 200 for “insufficient evidence,” appropriate only if it is a successful answer with no citations.
- Qdrant cleanup failure returns 503 after the document is already deleted; retries return 404.
- Streaming has no heartbeat, timeout, cancellation handling, or error event.

## 6. API consistency and contract recommendations

1. Define typed Pydantic response models for every endpoint and use `response_model`.
2. Introduce one authorization dependency policy per route, or explicitly document service-level checks and test them.
3. Enforce department scope inside document and analytics services, not just at the permission name level.
4. Make the chat contract explicit: distinguish `not_configured` (503) from `no_evidence` (200) and include a remediation field.
5. Return the existing document ID only if the caller is authorized to see that document; otherwise return a generic conflict.
6. Add cursor pagination and deterministic ordering for documents, conversations, users, and audit/feedback lists.
7. Add conversation message pagination and a delete endpoint with retention semantics.
8. Add audit and usage APIs only after events are actually recorded.
9. Add rate-limit and quota error contracts before exposing chat/upload externally.
10. Disable or protect OpenAPI docs in production.
11. Align paths with the documented API or update the documentation and client contracts to the actual paths.
12. Add idempotency keys for upload and invitation creation.

## 7. API scorecard

| Dimension | Score (1–5) | Rationale |
|---|---:|---|
| Route organization | 4 | Clear modules and consistent prefixing. |
| Envelope consistency | 4 | Success/error envelopes are coherent for handled paths. |
| Authentication | 3 | Multiple credential types work; refresh/rotation and browser flows have gaps. |
| Authorization | 1 | Confirmed scope leaks, missing checks, and dead authorization helper. |
| Contract completeness | 1 | Most response schemas missing; core chat is a placeholder. |
| Error handling | 3 | Central handlers are good; unhandled/503/429 contracts are weak. |
| Pagination/filtering | 2 | Basic page pagination only; no sorting/cursors. |
| OpenAPI quality | 2 | Routes are documented; response models and auth examples are incomplete. |
| Versioning | 3 | `/v1` prefix exists; no deprecation policy. |
| Browser parity | 1 | Home route broken; UI covers a small read-only subset. |

## 8. Priority endpoint fixes

### P0

1. Fix `cookies.et` and add `/` regression coverage.
2. Restrict document management to organization admins or the document’s department manager.
3. Restrict `grant_type: organization` to organization admins.
4. Scope analytics by department when `analytics:read_department` is used.
5. Add permission checks to department list/members and organization get.
6. Make chat return an honest, stable “not configured” response until retrieval exists; stop generating fake SSE tokens.

### P1

7. Add typed response schemas and accurate OpenAPI.
8. Enforce `chat:history_view` and define conversation permissions.
9. Paginate conversation messages and add message/citation loading limits.
10. Add idempotency and generic duplicate-document responses.
11. Add rate limiting for login, invitations, uploads, and chat.
12. Add audit events for security-sensitive endpoints.

### P2

13. Add cursor pagination, sorting, and filtering contracts.
14. Add API deprecation/version policy.
15. Add generated API clients and contract tests.

# 05 — Security Audit

## 1. Summary

The codebase shows several good security instincts: server-resolved tenancy, hashed API keys, parameterized ORM queries, filename sanitization, HttpOnly cookies, and ACL-aware document queries. Those strengths are undermined by known default secrets, department-scope authorization defects, missing permission checks, no audit trail, and development-grade operational controls.

**Security verdict:** not production-ready. The default secret and department-scope authorization defects are release blockers.

## 2. Scope, assets, and trust boundaries

### Assets

- Tenant documents and extracted content
- User credentials, password hashes, access/refresh tokens, API keys, invitation tokens
- Organization settings and model-provider credentials
- Document ACLs and department membership
- Audit/usage records
- Qdrant vectors and MinIO objects

### Actors

| Actor | Capability |
|---|---|
| Anonymous | Register only when no organization exists; login; accept invite; health/ready; OpenAPI docs |
| Employee | Read authorized documents, chat, history, feedback |
| Department manager | Employee capabilities plus department document management (intended scope) |
| Organization admin | Full tenant administration |
| Platform super-admin | Cross-tenant platform administration (intended, currently unreachable) |
| API-key holder | Scope-limited subset of the creating principal’s permissions |
| Operator | Infrastructure, database, Redis, Qdrant, MinIO access |

### Trust boundaries

1. Client → FastAPI
2. FastAPI → PostgreSQL
3. FastAPI → Redis
4. FastAPI → Qdrant
5. FastAPI → MinIO
6. API → Celery worker (intended; not connected)
7. Application → LLM/embedding provider (intended; not connected)

There is no TLS, mTLS, network policy, or service authentication inside the Compose topology. Stateful services are exposed on host ports.

## 3. Security findings summary

| ID | Severity | Finding |
|---|---|---|
| S1 | Critical | Known default application secret; `.env.example` does not require an override |
| S2 | Critical | Anyone who knows the default secret can forge access/refresh JWTs |
| S3 | High | Department managers can manage and delete documents outside their department |
| S4 | High | Department managers can create organization-wide ACL grants |
| S5 | High | `analytics:read_department` returns organization-wide analytics |
| S6 | High | Department list/members and organization get lack permission checks |
| S7 | High | No `super_admin` bootstrap; platform administration is unreachable |
| S8 | High | Soft-deleted departments retain document ACL access |
| S9 | High | Committed `.env.example` contains a real-looking database password |
| S10 | High | Upload validates extension only; no MIME/content/malware validation |
| S11 | High | No login throttling, lockout, or rate limiting |
| S12 | High | Missing FK/tenant check on `memberships.role_id` |
| S13 | High | No audit-event emission for security/business actions |
| S14 | High | Document deletion does not delete MinIO objects and commits before Qdrant cleanup |
| S15 | Medium | PBKDF2 iteration count is below current OWASP guidance |
| S16 | Medium | Refresh-token rotation is racy and non-atomic |
| S17 | Medium | JWT lacks issuer/audience validation and key rotation |
| S18 | Medium | Browser auth has no CSRF token, refresh flow, or security headers |
| S19 | Medium | Organization `settings` JSON is exposed to every member |
| S20 | Medium | Duplicate-upload error leaks document IDs across ACL boundaries |
| S21 | Medium | No prompt-injection, quota, or model-cost controls |
| S22 | Medium | OpenAPI docs/debug are enabled without production gating |
| S23 | Medium | Invitations are not email-bound or verified |
| S24 | Medium | Dependency and image supply chain is unpinned or inconsistent |
| S25 | Low | Logs omit request IDs and security events; no redaction policy |
| S26 | Low | No MFA or password reset/change flow |
| S27 | Low | API keys have no prefix/identification or rotation policy |
| S28 | Low | No explicit security headers (`CSP`, `HSTS`, `X-Content-Type-Options`) |

## 4. Critical findings

### S1/S2 — Known default JWT secret (Critical)

`app/core/config.py:27`:

```python
secret_key: str = "change-this-secret-before-deployment"
```

`.env.example` does not define `APP_SECRET_KEY`. A deployment that copies the example and starts the API uses the public default. `app/auth/token.py` signs and verifies HS256 tokens with this value. An attacker who knows a valid user UUID and organization UUID can forge an access token; if they know an active admin’s user ID, the forged token resolves to that admin because `resolve_principal` trusts the claims and re-loads the active membership.

Why this is critical:

- The secret is in source code and is not overridden by the example environment.
- There is no startup refusal for the default value.
- There is no minimum key length or entropy validation.
- Tokens have no issuer/audience binding and no key ID, so a leaked secret cannot be rotated gracefully.
- Access tokens are valid for 30 minutes by default; refresh tokens for 7 days.

Remediation:

1. Remove the default secret or fail startup when it is absent/default/short.
2. Require at least 32 random bytes (base64/hex) from a secret manager or environment.
3. Add a startup configuration test that rejects known placeholders.
4. Add `iss` and `aud` claims and verify them.
5. Add key IDs and a rotation plan.
6. Rotate the secret in any environment that used the default.

## 5. High findings

### S3 — Department managers are not scoped to their department (High)

`_can_manage` in `app/services/document_service.py:56-60`:

```python
return bool(
    principal.is_admin
    or {"document:manage_org", "document:manage_department"} & principal.permissions
)
```

It never checks:

- The document’s `department_id`
- The principal’s department membership
- Whether the principal is a manager of that specific department
- Whether the target department is active

`get_authorized_document` only checks read ACL access. A department manager who can read a document through any department ACL, ownership, or organization grant can then version, edit, move, delete, and replace ACLs on it. This breaks the intended department boundary.

Impact: cross-department document modification and deletion; possible data loss and ACL tampering.

Remediation:

- Introduce a `can_manage_document(principal, document)` policy.
- Allow organization admins and `document:manage_org`.
- Allow department managers only when `document.department_id` is in their managed department set.
- For documents with no department, require organization-level management permission.
- Test with two departments and managers in each.

### S4 — Organization-wide ACL escalation (High)

`replace_document_permissions` accepts `grant_type: "organization"`, sets `target_id = None`, and performs no organization-admin check. It then stores a `DocumentPermission` row with `grant_type="organization"`. The access filter matches any such row for every user in the organization:

```python
matching_acl = or_(
    DocumentPermission.user_id == user_id,
    DocumentPermission.department_id.in_(department_ids),
    DocumentPermission.grant_type == "organization",
)
```

A department manager can therefore grant `read`, `write`, or `admin` to every employee on any document they can manage. Even if `admin` does not currently confer management rights in code, it is a broad data-exposure grant and may become a management right later.

Remediation:

- Require `document:manage_org` or organization admin for `grant_type="organization"`.
- Validate that explicit user/department IDs are absent for organization grants.
- Add an ACL grant-type check constraint and uniqueness constraint.
- Audit ACL changes.

### S5 — Department analytics leak organization data (High)

`_authorize_analytics` accepts `analytics:read_department`, but `usage_analytics` and `document_analytics` query `principal.organization_id`, not a department. Any department manager sees organization-wide usage, cost, document, and ingestion metrics.

Remediation:

- Require a department parameter for department-scoped analytics.
- Validate that the principal manages or belongs to that department.
- Apply `DepartmentMember`, document `department_id`, and usage filters.
- Keep organization-wide analytics for `analytics:read_org`.

### S6 — Missing read permission checks (High)

- `list_departments` checks only tenant equality.
- `list_department_members` checks only tenant equality.
- `get_organization` checks only tenant equality.

Any authenticated employee can enumerate the organization’s department tree, member emails/names, and organization settings. The role catalog includes read permissions, but they are not enforced here. This is an information-disclosure and privacy issue.

Evidence: `app/services/department_service.py:26-42`, `app/services/department_service.py:130-153`, `app/services/organization_service.py:49-58`.

Remediation:

- Require `department:read_self`, `department:read_org`, or admin for department reads.
- Require `user:manage_org`, `user:manage_department` (scoped), or admin for member reads.
- Require `organization:read_self` or admin for organization get.
- Return only fields appropriate for the caller.

### S7 — No super-admin bootstrap (High availability/administration)

`Principal.is_super_admin` depends on the `super_admin` role. `DEFAULT_ROLE_PERMISSIONS` contains only `organization_admin`, `department_manager`, and `employee`. There is no seed script, startup hook, CLI command, or API path that creates a platform role or super-admin membership. `POST /organizations` requires `is_super_admin`.

Result: platform administration and multi-organization provisioning are unreachable in a normal deployment. Additionally, `create_organization` does not seed roles/permissions for the new tenant, so even if a super-admin existed, the new organization would have no usable roles until an admin is created by some out-of-band process.

Remediation:

- Add an idempotent bootstrap command (`python -m app.cli bootstrap-admin`) using a one-time secret.
- Seed the platform permission catalog and `super_admin` role.
- On organization creation, seed default roles and an initial organization admin (or return an invitation).
- Test the full bootstrap-to-invite flow.

### S8 — Deleted departments retain access (High)

Department deletion is only a soft delete. `DocumentRepository.access_filter` builds department IDs from `DepartmentMember` without joining `Department.deleted_at`. Members of a deleted department continue to satisfy department ACL grants. The department no longer appears in lists, and its members cannot be listed through the department endpoint, which makes the retained access non-obvious.

Remediation:

- Delete/inactivate memberships and department ACL grants in the same transaction.
- Or update the access filter to require `Department.deleted_at IS NULL` and active membership.
- Add a regression test: delete a department, then verify its members lose department-granted document access.

### S9 — Real-looking database password committed (High)

`.env.example` contains a non-placeholder `POSTGRES_PASSWORD` value (not reproduced here). The root `.gitignore` correctly ignores `.env`, but the example itself is tracked. Compose uses this value to build the API/worker `DATABASE_URL`, so a copied example runs with a committed credential. Even if the value is local-only, it normalizes insecure practice and may match a deployed database.

Remediation:

- Replace all example credentials with obvious placeholders.
- Add secret scanning to CI.
- Rotate any credential that was ever used outside local development.
- Separate local development defaults from deployment configuration.

### S10 — Upload validation is extension-only (High)

`validate_upload` checks:

- Sanitized filename extension is in a supported set
- Non-empty content
- Size limit

It does not check magic bytes/content type, parse the file, scan for malware, or enforce decompression limits. The client-provided MIME type is stored and later returned on download. Future extractors will process untrusted archives (DOCX/XLSX are ZIP containers), PDFs, and HTML.

Impact: malicious file storage, parser exploits, stored XSS if content is ever rendered, zip bombs during ingestion, malware distribution through the download endpoint.

Remediation:

- Verify file signatures for each supported type.
- Parse with resource/time limits in the worker, never in the request path.
- Add antivirus/CDR scanning before indexing.
- Enforce archive entry count, expanded size, compression ratio, and nesting limits.
- Serve downloads as `application/octet-stream` with `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`.
- Add HTML sanitization or refuse raw HTML rendering.

### S11 — No login throttling or lockout (High)

Login, registration, invitation acceptance, and refresh have no rate limiting, progressive delay, CAPTCHA, lockout, or IP/account anomaly detection. PBKDF2 slows each attempt but does not prevent distributed brute force or credential stuffing. There is no audit event for failed logins.

Remediation:

- Add per-IP and per-account rate limits at the edge and in the app.
- Add exponential backoff/lockout after repeated failures.
- Emit failed-login and lockout audit events.
- Add breached-password checks if policy allows.
- Consider MFA for administrators.

### S12 — Role tenant integrity is not enforced (High)

`Membership.role_id` has no foreign key. `resolve_principal` loads the role by ID without verifying `role.organization_id == organization_id`. A corrupt or cross-tenant membership row can grant another tenant’s role and permissions. Service-level invitation code normally writes matching IDs, but the database does not guarantee it.

Remediation:

- Add the FK.
- Validate role tenancy in `role_and_permissions`.
- Add a test that a cross-tenant role ID is rejected.
- Consider composite `(organization_id, role_id)` constraints.

### S13 — No audit trail (High)

`AuditLog` and `AuditRepository` exist, but no service writes audit events. Login, logout, invitation, role/status change, organization update, ACL change, document download, document delete, and API-key creation/revocation are not recorded. `audit:read_org` is a default admin permission, but there is no audit API.

Impact: no forensic reconstruction, no accountability for destructive actions, no compliance evidence, and no way to detect ACL tampering.

Remediation:

- Add an `audit_service.record(...)` call at security-sensitive service boundaries.
- Include actor, organization, action, target, request ID, IP, result, and safe metadata.
- Do not log secrets or document content.
- Add read APIs with pagination and retention.
- Make audit writes part of the same transaction where practical, or use an outbox.

### S14 — Incomplete document deletion (High)

`delete_document`:

1. Marks the row deleted.
2. Commits.
3. Attempts Qdrant cleanup.
4. Never deletes MinIO objects or prior versions.

Consequences:

- Sensitive content remains in object storage after API deletion.
- Orphan vectors remain if Qdrant fails; the API returns 503 but the document is unreachable for retry.
- Storage costs grow indefinitely.
- “Deleted” documents may still be recoverable by an operator with object-store access.

Remediation:

- Implement a deletion saga/outbox with states: pending, storage_deleted, vectors_deleted, completed.
- Delete all MinIO version objects idempotently.
- Delete Qdrant points idempotently.
- Add a reconciliation worker and an admin repair endpoint.
- Define retention and legal-hold exceptions.

## 6. Medium findings

### S15 — Password hashing parameters (Medium)

PBKDF2-HMAC-SHA256 with 310,000 iterations (`app/core/security.py:11-20`) is below the OWASP 2023 recommendation of 600,000 for this construction. It is still costly, and the implementation uses a random 16-byte salt and `hmac.compare_digest`, which are good.

Remediation: raise iterations, store/verify the iteration count (already encoded), rehash on successful login when parameters change, and re-evaluate Argon2id.

### S16 — Refresh rotation race (Medium)

`refresh` checks Redis for revocation, validates the user/membership, then calls `revoke_token`. Two concurrent requests can both observe the token as valid before either revoke commits, producing two new token pairs. An attacker with a stolen refresh token can race the legitimate client.

Remediation: use an atomic Redis `SET NX`/Lua compare-and-set on the refresh `jti`, store a rotation family, and revoke the family on reuse detection.

### S17 — JWT hardening (Medium)

- No `iss`, `aud`, `nbf`, or clock-skew handling.
- No key ID or rotation.
- Secret length is not validated.
- Token size is unbounded.
- `iat` is not validated.
- Access token revocation relies solely on Redis availability; Redis failure returns 503 for all token auth.

Remediation: add standard claims, validate them, cap token size, use a keyring with `kid`, and define Redis failure behavior.

### S18 — Browser auth and headers (Medium)

- No CSRF token on login/logout/browser forms.
- SameSite=Strict is the main CSRF defense.
- No refresh cookie, so the browser session ends after 30 minutes.
- No security headers (`CSP`, `HSTS`, `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`).
- `/docs` is linked from the UI for all authenticated users.
- `secure` cookie flag depends on `APP_ENVIRONMENT == "production"`; a mis-set environment quietly disables it.

Remediation: add CSRF tokens for cookie-authenticated state changes, use a `__Host-` cookie, add security headers middleware, add a refresh flow or explicit re-login, and gate API docs.

### S19 — Organization settings exposure (Medium)

Every member can read the full `organization.settings` JSON through `GET /organizations/{id}`. If this object later holds provider keys, retention policy, webhook secrets, or feature flags, the exposure becomes severe. No schema or redaction exists.

Remediation: split public organization metadata from sensitive settings, validate allowed keys, and restrict sensitive settings to admins.

### S20 — Duplicate-upload oracle (Medium)

The 409 response includes the existing document UUID. A user with upload permission can test guessed file contents and learn IDs of documents they cannot read. This is a cross-ACL information leak and can aid targeted attacks on document endpoints.

Remediation: return a generic conflict without the ID, or only include the ID when the caller is authorized to read the existing document.

### S21 — No prompt-injection or model-abuse controls (Medium)

RAG generation is not implemented, but the future design must treat retrieved documents and user questions as untrusted. There are no:

- Input/output token limits
- Per-tenant quotas
- Cost controls
- Prompt-injection defenses
- Retrieval allowlists/ACL re-checks at generation time
- Citation verification
- Output moderation
- Model-provider key isolation

Remediation: define these before enabling chat, not after. Re-check document ACLs at retrieval time and verify every citation against an authorized chunk.

### S22 — OpenAPI/debug exposure (Medium)

`/docs`, `/redoc`, and `/openapi.json` are public by default; the UI links directly to `/docs`. `APP_DEBUG` defaults to false, but if enabled it may expose stack traces. There is no environment gate.

Remediation: disable or protect docs outside development; never enable debug in production; add a startup assertion.

### S23 — Invitations are bearer tokens, not email-bound (Medium)

`accept_invitation` validates only the token and activates the invited user. It does not check that the accepting person controls the invited email address. The token is returned in the API response and is not emailed. Anyone who obtains it can set the password and activate the account.

Remediation: send a one-time link to the invited address, bind acceptance to an email verification step, shorten expiry, and audit acceptance. Consider requiring the inviter to confirm identity out of band.

### S24 — Dependency and image supply chain (Medium)

- `minio/minio:latest` is unpinned.
- `httpx2>=2.0,<3` appears in dev dependencies; this is likely a typo for `httpx` and should be verified.
- Dependency ranges use lower bounds rather than a lock file.
- No CI dependency audit, SBOM, or image scanning.
- AI extras are not installed by the Dockerfile, so production and development dependency sets differ.

Remediation: pin images by digest, add a lock file, run `pip-audit`/OSV scanning, publish SBOMs, and make the Docker dependency set explicit.

### S25 — Logging and monitoring (Low/Medium)

There is no logging configuration, no request-ID propagation into log records, and no redaction policy. `logger.exception` calls can include storage keys and tenant IDs, but not secrets. Failed logins and permission denials are not recorded. No metrics/tracing exist.

Remediation: structured JSON logs with request/tenant/user/action fields, redaction for tokens/keys/content, security-event logging, and alerts.

### S26 — Account lifecycle (Low/Medium)

No password change, password reset, MFA, session listing, or device revocation. Users cannot recover accounts. Admins cannot reset credentials except by re-inviting, and soft-deleted emails cannot be re-invited due to uniqueness.

Remediation: add password reset/change with token revocation, admin reset, optional MFA, and session management.

### S27 — API key lifecycle (Low)

API keys are high-entropy and hashed, which is good. There is no key prefix/identifier, last-used timestamp, rotation workflow, maximum lifetime, or user-visible creation audit. An admin can list all tenant keys but not see usage.

Remediation: add prefixes for identification, last-used tracking, expiry defaults, rotation, and audit events.

### S28 — Security headers (Low)

No HSTS, CSP, frame protection, MIME sniffing protection, referrer policy, or permissions policy. Jinja autoescaping is enabled by default, and no template uses `|safe`, which is a strength.

Remediation: add middleware with conservative headers; keep `/docs` CSP compatible or disable docs.

## 7. Security controls that are implemented well

| Control | Evidence | Assessment |
|---|---|---|
| Server-resolved tenancy | `Principal` built from token/API key; paths checked | Strong design |
| Parameterized SQL | SQLAlchemy expressions throughout; no string-built SQL for user values | Strong |
| Hashed API keys | SHA-256 of high-entropy secret; only hash stored | Good |
| API-key scopes | Subset of creator permissions; intersection at use | Good |
| Refresh/access separation | Token `type` claim checked | Good |
| Token revocation | Redis `jti` deny-list | Good, with availability caveat |
| Password hashing | PBKDF2, per-password salt, constant-time compare | Good construction, tune cost |
| Filename sanitization | Basename + character allowlist + length cap | Good |
| Upload size limit | Configurable, enforced during read | Good |
| ACL denied check | Deny overrides access, including admin document access | Good |
| Jinja autoescaping | No `|safe` usage | Good |
| HttpOnly/SameSite cookie | `httponly=True`, `samesite="strict"` | Good baseline |
| Duplicate content detection | SHA-256 per tenant | Good, needs race-safe index |
| Audit/usage models | Present and indexed | Good foundation, unused |

## 8. Tenant isolation assessment

| Path | Isolation mechanism | Assessment |
|---|---|---|
| Login | User + organization active, membership active | Good |
| Principal resolution | User, organization, membership all tenant-consistent | Good, except role FK |
| Users | Organization filter on queries | Good |
| Departments | Organization filter, parent/target validation | Read permissions missing |
| Documents | Organization + ACL `EXISTS` | Good ACL mechanics; department scope flawed |
| Document ACL targets | Organization validation except organization grants | Organization grant escalation |
| Conversations | `(organization_id, user_id)` ownership | Good |
| Feedback | Owned conversation + message | Good |
| Ingestion | Organization + authorized document | Good |
| Analytics | Organization only | Department scope not applied |
| Admin metrics | Org-scoped unless super-admin | Good intent, super-admin unreachable |
| Audit | Organization-scoped repository | No writers |

Database-level tenant isolation is not enforced. There is no RLS and no composite tenant foreign keys. Application filtering is the only guarantee.

## 9. Threat scenarios

### Scenario A — Forged administrator token

1. Attacker learns the default secret from source.
2. Attacker obtains an admin user UUID (invite response, user list, logs, or a misconfigured client) and organization UUID.
3. Attacker signs an HS256 access token with `sub=admin_uuid`, `org=org_uuid`, `type=access`, future `exp`.
4. `resolve_principal` verifies the signature, loads the active admin membership, and grants admin permissions.

Mitigation: eliminate default secret, validate secret at startup, add key rotation and standard claims.

### Scenario B — Department manager escalation

1. Department A manager has `document:manage_department`.
2. A document from Department B is shared read-only to Department A.
3. Manager B uses `PUT /documents/{id}/permissions` with `grant_type=organization`.
4. All employees gain read access; manager can also delete or replace the document.

Mitigation: scope management and organization grants by role and department.

### Scenario C — Deleted department continues to grant access

1. Admin deletes Department A.
2. Members remain in `department_members`.
3. An ACL grant for Department A remains.
4. Former members still read those documents through the department ACL.

Mitigation: cascade/inactivate memberships and ACL grants, or join to active department state.

### Scenario D — Malicious upload

1. User uploads a DOCX/PDF with a valid extension but malicious content or a zip bomb.
2. Storage accepts it because only extension/size are checked.
3. Future ingestion parses it in the worker without resource limits.
4. Worker memory/CPU exhaustion or parser compromise.

Mitigation: magic-byte checks, sandboxed parsing with limits, malware scanning, worker isolation.

## 10. Security remediation priority

### Release blockers

1. Remove/fail on the default JWT secret; rotate secrets.
2. Enforce department scope for document management and analytics.
3. Restrict organization-wide ACL grants to organization admins.
4. Add missing department/organization read permission checks.
5. Remove committed credentials and add secret scanning.
6. Add a super-admin bootstrap and organization role provisioning.
7. Fix department deletion access revocation.
8. Implement document deletion including MinIO and Qdrant.
9. Add audit events for authentication and destructive operations.

### Before external exposure

10. Add login/upload/chat rate limits and lockout.
11. Add MIME/content/malware validation and sandboxed parsing.
12. Add CSRF/security headers and production docs gating.
13. Add refresh-token atomic rotation.
14. Add JWT issuer/audience/key rotation.
15. Add retention/deletion policy and storage lifecycle rules.
16. Add structured security logging and alerting.

### Next maturity stage

17. Add MFA and password reset.
18. Add API-key lifecycle management.
19. Add dependency/image scanning and SBOMs.
20. Add prompt-injection defenses, quotas, and citation verification.
21. Consider RLS and composite tenant constraints.
22. Add formal threat modeling and penetration testing.

## 11. Security scorecard

| Dimension | Score (1–5) | Rationale |
|---|---:|---|
| Authentication | 3 | Solid token/password mechanics; default secret and no throttling are serious. |
| Authorization | 1 | Confirmed scope leaks and missing checks. |
| Tenant isolation | 3 | Good application filters; weak database guarantees. |
| Secrets management | 1 | Default JWT secret and committed DB credential. |
| Input validation | 2 | Pydantic and filename checks are good; file content validation is absent. |
| Data protection at rest/in transit | 1 | No TLS, encryption, retention, or secure deletion controls. |
| Auditability | 1 | No emitted audit events. |
| Session/token lifecycle | 3 | Revocation exists; rotation and browser refresh are weak. |
| Dependency/operational security | 1 | Unpinned images, no scans, exposed services. |
| Security testing | 1 | No security test suite or integration coverage. |

## 12. Conclusion

The application’s authorization model has a good conceptual foundation but is not consistently enforced. The most urgent work is to make department scope real, remove known secrets, enforce permissions on read endpoints, and establish audit and deletion guarantees. Until those are complete, the system should not hold production documents or be exposed outside a trusted development network.

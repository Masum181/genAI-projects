# 07 — Performance Analysis

## 1. Summary

No runtime benchmarking was possible because dependencies and infrastructure are unavailable. This assessment is based on query paths, index coverage, serialization, blocking work, and external calls in the code. The most important findings are structural: every authenticated request performs several sequential database and Redis operations, password hashing blocks the async event loop, uploads buffer entire files in memory, conversation history is unbounded, and ACL predicates lack supporting indexes.

**Performance verdict:** acceptable for local development with one user and small data; likely to degrade sharply under concurrent users or document volume.

## 2. Method and limitations

- Static review of route → service → repository paths.
- Query count derived by tracing executed repository methods.
- Index assessment from ORM metadata and query predicates.
- No load tests, profiling, query plans, or production telemetry.
- No dependencies installed, so no runtime microbenchmarks.
- No claim is made about absolute throughput or latency; those require measurement.

## 3. Hot path: authenticated request

Every protected request goes through `get_current_principal` before the route handler:

1. `find_active_membership_context`:
   - `SELECT` user
   - `SELECT` organization
   - `SELECT` membership
2. `role_and_permissions`:
   - `Session.get(Role, role_id)`
   - `SELECT` permission names joined through `role_permissions`
3. Redis `EXISTS revoked-token:{jti}` (JWT path), or one API-key lookup for `X-API-Key`.

**Typical cost:** 5 PostgreSQL round trips + 1 Redis round trip per request. API-key requests add a sixth database query. There is no caching of identity, roles, or permissions.

For a page that loads 10 API resources, that is 50 identity queries plus 10 resource queries. For browser pages that issue separate document/conversation requests, the same overhead repeats.

### Recommendation

- Cache the resolved principal (user, org, role, permissions) in Redis for 30–60 seconds, keyed by token `jti` or a hash of the API key, with explicit invalidation on role/status/permission changes.
- Or combine user/organization/membership/role/permissions into fewer joined queries.
- Make Redis revocation-check failure policy explicit; a Redis outage currently makes all auth fail closed with 503.

## 4. Blocking work on the async event loop

### 4.1 PBKDF2 password hashing (High)

`hash_password` and `verify_password` use 310,000 PBKDF2-HMAC-SHA256 iterations synchronously inside async request handlers:

- `POST /auth/login`
- `POST /auth/register`
- `POST /auth/accept-invite`
- Browser `POST /login`

PBKDF2 is intentionally CPU-heavy. It blocks the event loop for the duration of the derivation, preventing other requests in the same worker from progressing. A burst of login attempts can therefore stall unrelated API traffic.

**Remediation:** run hashing in a thread pool (`asyncio.to_thread` / `run_in_threadpool`), or use a worker/queue for authentication. Keep iteration count high; do not lower it to mask the blocking issue.

### 4.2 Upload hashing and full-file reads (Medium/High)

`UploadFile.read(max + 1)` reads the entire file up to 25 MiB into memory. SHA-256 is then computed synchronously, and the bytes are passed to MinIO through a `BytesIO`.

Per concurrent upload, memory is roughly `file size × copies` (upload buffer, hash input, MinIO buffer). At 25 MiB and modest concurrency, this can exhaust worker memory.

**Remediation:** stream to a temporary file or directly to MinIO in chunks, compute the hash incrementally, enforce per-tenant concurrency limits, and use server-side multipart upload for larger limits.

## 5. Query cost by endpoint

| Endpoint | Approx. DB queries | Notes |
|---|---:|---|
| `GET /health` | 0 | Liveness only. |
| `GET /ready` | 1 DB + Qdrant | Every probe opens a DB connection and calls Qdrant. |
| `POST /auth/login` | 2 + PBKDF2 | Candidate lookup, membership; CPU-bound. |
| `POST /auth/refresh` | 3 + Redis | User, membership, Redis exists, revoke write, token issuance. |
| `GET /auth/me` | 5 + Redis | Identity resolution dominates. |
| `GET /documents` | 7 + Redis | Identity + count + page; ACL `EXISTS` predicates. |
| `GET /documents/{id}` | 6 + Redis | Identity + authorized document. |
| `POST /documents/upload` | 7–8 + MinIO | Identity, department check, duplicate check, flush/commit. |
| `GET /organizations/{id}/users` | 7 + Redis | Identity + count + page. |
| `GET /organizations/{id}/departments` | 7 + Redis | Identity + count + page. |
| `GET /conversations` | 7 + Redis | Identity + count + page. |
| `GET /conversations/{id}` | 8 + Redis | Adds messages + citations; both unbounded. |
| `GET /admin/analytics/usage` | 6 + Redis | Identity + aggregate. |
| `GET /admin/metrics` | 10 + Redis | Identity + org + four aggregates. |
| `POST /chat` | 8+ + Redis | Identity, conversation, indexed count, message writes; stub. |

Query counts are approximate and exclude lazy loads. Because `expire_on_commit=False`, attributes remain usable after commit, but code also calls `refresh` frequently after writes.

## 6. Database performance

### 6.1 Missing indexes (High)

The ACL filter is the dominant document-query cost. It references:

- `department_members.user_id`
- `document_permissions.user_id`
- `document_permissions.department_id`
- `document_permissions.permission`
- `document_permissions.grant_type`
- `documents.owner_user_id`

Current composite index on `document_permissions` starts with `document_id`, so it does not help the ACL `EXISTS` predicates. `department_members` has a unique `(department_id, user_id)` index, which does not help user-first lookup. API-key lookup by hash has no unique index. Message and citation foreign keys are unindexed.

See `03-database-analysis.md` Section 7 for the full list.

### 6.2 ACL `EXISTS` design

`DocumentRepository.access_filter` builds a correlated `EXISTS` for allowed grants and another for denied grants, with a subquery over department memberships. For each candidate document, PostgreSQL may evaluate these subqueries. With small data this is fine; with millions of ACL rows it can be expensive.

**Remediation:**

- Add targeted indexes.
- Consider a materialized effective-access view per user/document if access checks dominate.
- Benchmark `EXISTS` vs `JOIN` plans with realistic tenant sizes.
- Ensure `ANALYZE` runs after bulk ACL changes.
- Consider caching effective document IDs per user for short TTLs.

### 6.3 Pagination counts

Every paginated endpoint executes a separate `COUNT(*)` over the filtered statement. Count queries on ACL-heavy document lists can be as expensive as the page query. This is acceptable at small scale but not free.

**Remediation:** allow `include_total=false`, use approximate counts for large tenants, or switch to cursor pagination.

### 6.4 Unbounded conversation history

`get_conversation` loads all messages and all citations for those messages, with no pagination or limit. A long chat can return thousands of rows in one response and load all citation objects into memory.

**Remediation:** paginate messages, cap the initial window, load citations only for the displayed messages, and add `(conversation_id, created_at)` and `(message_id)` indexes.

### 6.5 Department cycle and hierarchy queries

Department listing returns all departments in one paginated query. There is no recursive path query yet. If future authorization traverses ancestors, the missing cycle prevention will worsen query complexity and may create loops.

### 6.6 UUIDv7 as primary key

UUIDv7 is time-sortable and improves index locality versus random UUIDv4. This is a performance strength, assuming the database and driver preserve it.

## 7. External service performance

### 7.1 MinIO

- A new `MinioStorage`/`Minio` client is constructed per upload/download/delete.
- `bucket_exists` is called on every upload, adding a network round trip.
- `make_bucket` can race between concurrent first uploads.
- Uploads and downloads buffer complete objects in memory.
- No explicit timeouts or connection-pool limits are configured.

**Remediation:** share one MinIO client per process, create the bucket during startup, add retries/timeouts, stream objects, and add per-tenant concurrency limits.

### 7.2 Qdrant

- The client is process-global and created at startup; that is good.
- Collection creation and payload-index checks run at startup only; also good.
- No actual search path exists, so search latency cannot be assessed.
- Future retrieval must apply organization and ACL filters. Large authorized-document ID lists can make filters expensive.

**Remediation:** design ACL-aware filters before implementation, consider storing department/ACL principals in payload, and benchmark top-k search with realistic filters.

### 7.3 Redis

- One Redis client is created at startup.
- Every JWT request performs an `EXISTS`; every refresh/logout performs `SETEX`.
- No socket connect/read timeouts, health check, retry policy, or pool size configuration.
- Redis is also the Celery broker/backend; a shared outage affects auth and jobs.
- No local cache or circuit breaker for revoked-token checks.

**Remediation:** configure timeouts and retries, separate auth Redis from Celery if needed, cache identity, and define fail-open/fail-closed behavior per endpoint.

## 8. Background processing performance

Celery has no registered task, no retry policy, no concurrency setting, no `acks_late`, no prefetch limit, no rate limits, and no dead-letter strategy. There is no ingestion workload to profile. When implemented:

- Ingestion must be chunked and idempotent.
- Embedding batches should be bounded by provider limits.
- Qdrant upserts should use batches and wait policies.
- Job progress should be recorded without long transactions.
- Large files must not be loaded entirely into worker memory.

## 9. Caching opportunities

| Data | Cache | Invalidation |
|---|---|---|
| Principal/role/permissions | Redis, 30–60s | Role, membership, user status, permission change |
| Organization settings | Redis or request scope | Organization update |
| Department tree | Redis per org | Department create/update/delete |
| Document metadata | Optional | Document update/delete/ACL change |
| API-key lookup | Redis hash→metadata | Key revoke/expiry |
| Embeddings | Persistent cache by content hash | Never (content-addressed) |
| Retrieval results | Optional per query + ACL fingerprint | ACL/document index change |

Caching is not free: permissions and ACLs are security-sensitive and must be invalidated reliably. Start with principal caching and measure.

## 10. Connection pool and timeout configuration

- SQLAlchemy engine uses default pool size/overflow (typically 5 + 10) and `pool_pre_ping=True`.
- No `pool_timeout`, `pool_recycle`, statement timeout, or server-side query timeout is configured.
- No request timeout middleware.
- Redis and MinIO clients lack explicit timeouts.
- Qdrant client uses library defaults.

Under concurrency, a 5-query auth path can exhaust a small pool quickly, and a slow external call can hold a connection for the request duration.

**Remediation:** configure pool sizes per process, set connect/read/statement timeouts, add request deadlines, and avoid holding DB sessions across MinIO/Qdrant calls.

## 11. Payload and serialization performance

- `serialize_model` iterates columns and converts UUID/datetime/Decimal one field at a time; fine at small scale.
- Document listing returns all document columns, including storage key, file hash, and metadata; clients may not need all.
- Conversation detail returns full message content and citations with no limit.
- Analytics returns aggregates; fine.
- JSONB settings/ACL scopes are not size-limited, allowing large payloads.

## 12. Scalability risks

| Risk | Trigger | Impact |
|---|---|---|
| Auth query amplification | Concurrent authenticated traffic | DB saturation and high p95 latency |
| Blocking PBKDF2 | Login bursts/credential stuffing | Event-loop stalls for unrelated requests |
| ACL scans | Many documents/ACL rows | Slow document lists and counts |
| Unbounded history | Long conversations | Memory spikes and slow responses |
| In-memory uploads | Concurrent large uploads | Worker OOM |
| Redis dependency | Redis latency/outage | All auth requests slow or fail |
| No query timeouts | Slow SQL/locks | Pool exhaustion |
| New MinIO client per call | High upload/download volume | Socket/FD pressure |
| Missing worker contract | Ingestion enabled later | Queue backlog, duplicate work, retries without idempotency |

## 13. Recommended measurement plan

Before optimizing, establish baselines:

1. Seed a synthetic tenant with 10k documents, 100 departments, 100k ACL rows, 1M messages, and 1M usage records.
2. Measure p50/p95/p99 for login, principal resolution, document list, document detail, conversation detail, upload, and analytics.
3. Capture `EXPLAIN (ANALYZE, BUFFERS)` for ACL document queries.
4. Load test with 10/50/100 concurrent users and a realistic read/write mix.
5. Measure DB pool wait time, Redis latency, MinIO latency, and event-loop lag.
6. Test PBKDF2 under concurrency and confirm event-loop blocking.
7. Test ACL changes and cache invalidation correctness.
8. Only then add indexes/caches and remeasure.

## 14. Prioritized performance actions

### P0

1. Move password hashing off the event loop.
2. Add the missing ACL/API-key/message indexes.
3. Paginate conversation messages and citations.
4. Stream uploads instead of reading full files into memory.
5. Configure connection pool sizes and timeouts.

### P1

6. Cache resolved principals with correct invalidation.
7. Consolidate principal queries.
8. Share MinIO clients and create the bucket at startup.
9. Add request deadlines and external-service timeouts.
10. Add query-plan tests for ACL-heavy document lists.

### P2

11. Add cursor pagination and optional totals.
12. Add embeddings/retrieval caches.
13. Design ACL-aware Qdrant filtering and benchmark it.
14. Add observability for pool waits, event-loop lag, and external latency.
15. Consider read replicas or partitioning for usage/audit/messages at scale.

## 15. Performance scorecard

| Dimension | Score (1–5) | Rationale |
|---|---:|---|
| Authentication cost | 2 | Five queries + Redis per request; no caching. |
| Event-loop friendliness | 2 | Blocking password hashing and file hashing. |
| Database indexing | 2 | Core tenant indexes exist; ACL/key/message paths weak. |
| Query efficiency | 2 | Several sequential queries and count queries per page. |
| Memory behavior | 2 | Full-file buffering and unbounded history. |
| External-service efficiency | 2 | Per-request MinIO client, no timeouts. |
| Background processing | 1 | No worker implementation to assess. |
| Caching | 1 | None implemented. |
| Observability for performance | 1 | No metrics, traces, or query timing. |
| Measured evidence | 1 | None; no load tests or profiles. |

## 16. Conclusion

The system is likely fine for a demo with a small dataset. It is not positioned for production concurrency. The highest-leverage changes are inexpensive: add the missing indexes, paginate history, stream uploads, configure timeouts, and move password hashing off the event loop. Principal caching should follow once invalidation semantics are defined.

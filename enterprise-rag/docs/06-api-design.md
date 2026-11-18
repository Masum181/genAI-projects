# 06. API Design Specification

## 1. API conventions
- Base path: `/api/v1`
- JSON request and response payloads.
- Auth via cookie or bearer JWT.
- All mutating endpoints require `Idempotency-Key` for non-idempotent writes when practical.
- Response envelope format:
```json
{
  "success": true,
  "request_id": "req_123456",
  "data": {},
  "error": null
}
```

## 2. Common error format
```json
{
  "success": false,
  "request_id": "req_123456",
  "error": {
    "code": "FORBIDDEN",
    "message": "User does not have access to this document.",
    "details": {
      "resource": "document:uuid"
    }
  }
}
```

## 3. Authentication API
### POST /api/v1/auth/login
- Purpose: Authenticate a user and return session or JWT.
- Required permission: none.
- Body:
```json
{
  "email": "user@company.com",
  "password": "StrongPassword123!"
}
```
- Success: `200 OK` with access token and org context.
- Error: `401 UNAUTHORIZED`.

### POST /api/v1/auth/logout
- Purpose: Revoke current session.
- Authorization: required.

### POST /api/v1/auth/refresh
- Purpose: Refresh an access token.
- Authorization: required.

## 4. Organization API
### GET /api/v1/organizations
- Purpose: List organizations for a super admin.
- Permission: `organization:read_all`

### POST /api/v1/organizations
- Purpose: Create a new tenant.
- Permission: `organization:create`

### GET /api/v1/organizations/{organization_id}
- Purpose: Fetch tenant details.
- Permission: `organization:read_self`

## 5. User API
### GET /api/v1/users/me
- Purpose: Get current user profile.
- Permission: authenticated user.

### GET /api/v1/organizations/{organization_id}/users
- Purpose: List users in an organization.
- Permission: `user:manage_org` or `organization:read_self`

### POST /api/v1/organizations/{organization_id}/users/invite
- Purpose: Invite a new member.
- Permission: `user:invite`

## 6. Department API
### GET /api/v1/organizations/{organization_id}/departments
- Purpose: List all departments.
- Permission: `department:read_self` or org role.

### POST /api/v1/organizations/{organization_id}/departments
- Purpose: Create a department.
- Permission: `department:manage_org`

## 7. Document API
### POST /api/v1/organizations/{organization_id}/documents/upload
- Purpose: Initiate upload and create a document record.
- Permission: `document:upload`
- Body:
```json
{
  "title": "Employee Handbook 2025",
  "document_type": "pdf",
  "department_id": "dept_123",
  "category": "policy",
  "metadata": {"owner": "HR"}
}
```
- Response includes `upload_url` and `document_id`.

### GET /api/v1/documents/{document_id}
- Purpose: Fetch document metadata.
- Permission: `document:read_authorized`

### PATCH /api/v1/documents/{document_id}
- Purpose: Update document metadata or replace a file version.
- Permission: `document:manage_org` or `document:manage_department`

### DELETE /api/v1/documents/{document_id}
- Purpose: Soft delete a document and trigger vector cleanup.
- Permission: `document:manage_org`

## 8. Document permission API
### GET /api/v1/documents/{document_id}/permissions
- Purpose: List current ACLs.
- Permission: `document:manage_org`

### PUT /api/v1/documents/{document_id}/permissions
- Purpose: Replace document permissions.
- Permission: `document:manage_org`

## 9. Ingestion job API
### GET /api/v1/ingestion-jobs/{job_id}
- Purpose: Check ingestion status.
- Permission: `document:read_authorized` or admin.

### GET /api/v1/documents/{document_id}/ingestion-jobs
- Purpose: List associated ingestion jobs.
- Permission: document owner/admin.

## 10. Chat API
### POST /api/v1/chat
- Purpose: Ask a question and receive grounded answer.
- Permission: `chat:ask`
- Set `stream` to `true` to receive the answer as server-sent events.
- Request:
```json
{
  "conversation_id": "conv_abc",
  "question": "What is the reimbursement policy for international travel?",
  "stream": false
}
```
- Response:
```json
{
  "conversation_id": "conv_abc",
  "answer": "Travel reimbursement is capped at ...",
  "citations": [
    {
      "document_id": "doc_123",
      "document_title": "Travel Policy",
      "page": 14,
      "excerpt": "Employees may claim reimbursement..."
    }
  ]
}
```

### GET /api/v1/conversations/{conversation_id}
- Purpose: View conversation history.
- Permission: `chat:history_view`

### POST /api/v1/chat/stream
- Purpose: SSE streaming answer.
- Permission: `chat:ask`
- Frames use `event: token` for answer text and `event: end` for status,
  citations, and confidence. Each frame includes the conversation, request, and
  assistant message IDs.
- Streaming currently sends buffered answer text after generation and validation;
  it does not expose provider token-by-token generation.

## 11. Feedback API
### POST /api/v1/feedback
- Purpose: Submit answer feedback.
- Permission: `feedback:create`
- Body:
```json
{
  "conversation_id": "conv_abc",
  "message_id": "msg_123",
  "feedback_type": "thumbs_down",
  "note": "Citation was incorrect."
}
```

## 12. Analytics API
### GET /api/v1/admin/analytics/usage
- Purpose: Aggregate usage and cost metrics.
- Permission: `analytics:read_org`

### GET /api/v1/admin/analytics/documents
- Purpose: Track document ingestion and indexing health.
- Permission: `analytics:read_org`

## 13. Administration API
### GET /api/v1/admin/health
- Purpose: Platform health summary.
- Permission: `platform:read_all` or admin service role.

### GET /api/v1/admin/metrics
- Purpose: Operational metrics.
- Permission: `platform:read_all`

## 14. Pagination, filtering, sorting
- Use `page`, `page_size`, `sort_by`, and `sort_order` query parameters.
- Example: `/api/v1/documents?page=2&page_size=25&sort_by=updated_at&sort_order=desc`
- Filters should be explicit fields such as `status`, `department_id`, `owner_user_id`, and `document_type`.

## 15. API versioning and rate limits
- API versioning via `/api/v1` prefix.
- Rate limits based on tenant and user ID; defaults set per role type.
- Use `429 Too Many Requests` when limits are exceeded.

## 16. SSE streaming conventions
- Content-Type: `text/event-stream`
- Emit `event: token` and `event: end` messages.
- Include `conversation_id` and `request_id` on every stream frame.

## 17. Validation rules
- Uploaded file names sanitized and extension validated.
- Document type restricted to supported list.
- Role IDs and department IDs must exist in the tenant.
- Reject ambiguous or mismatched tenant IDs.

## 18. Related documents
- [05-database-design.md](./05-database-design.md)
- [03-roles-and-permissions.md](./03-roles-and-permissions.md)
- [openapi-design-guidelines.md](./openapi-design-guidelines.md)

## 19. Current API and browser implementation
The FastAPI application currently mounts the following API groups under `/api/v1`:
authentication and API keys; organizations and users; departments and department
members; document upload, versions, metadata, download, deletion, and ACLs; ingestion
job status; conversations, chat, and feedback; analytics; and administrative health
and metrics. Authenticated API responses use the success envelope described above,
and errors include a request ID.

Document uploads use `multipart/form-data` (`file`, `title`, optional
`document_type`, and optional `department_id`) and return an accepted document and
ingestion-job ID. Downloads use `GET /documents/{document_id}/download`; ACLs are
replaced with `PUT /documents/{document_id}/permissions`. The browser UI is served
at `/login`, `/ui/`, `/ui/documents`, and `/ui/conversations`.

Document uploads create a queued ingestion job and publish it to the Celery worker.
The worker extracts supported PDF, DOCX, XLSX, TXT, and HTML files, creates
overlapping text chunks and embeddings, upserts tenant-scoped points into Qdrant,
and records indexed chunks and job state in PostgreSQL. Poll the ingestion-job
endpoint to confirm whether processing succeeded; queue, extraction, embedding,
or Qdrant failures are recorded and retried before being dead-lettered. The API
and worker images install the `ai` extra for the configured Sentence Transformers
embedding provider.

Chat resolves current indexed document versions through tenant and document ACL
filters before dense Qdrant and PostgreSQL full-text retrieval. It fuses the
rankings, verifies candidate chunks against PostgreSQL again, reranks the
authorized evidence, and validates generated citation IDs against evidence sent
to the model. Answers, citations, and usage are persisted with the conversation.
No matching authorized evidence produces an insufficient-evidence answer;
unavailable retrieval or generation providers produce `503` responses.

The default answer provider is Ollama; OpenAI and Gemini adapters are available
when their optional dependencies and credentials are configured. Embeddings use
Sentence Transformers. Document ingestion alone is not sufficient: the embedding,
Qdrant, retrieval, and generation providers must also be configured and available.

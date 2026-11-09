# Data Dictionary

## Core domain fields
- `organization_id`: tenant owner for all scoped records.
- `document_id`: canonical identifier for a document.
- `document_version_id`: immutable record for a specific file revision.
- `department_id`: department scope for resource access.
- `user_id`: application user identifier.
- `request_id`: correlation id for API and job traces.
- `status`: lifecycle status field used across tables.
- `content_hash`: integrity check for duplicate detection.
- `deleted_at`: logical deletion marker for soft-deletes.

## Entity-by-entity definitions
- `organizations`: top-level tenant record and platform isolation boundary.
- `users`: end-user identity and account state.
- `memberships`: mapping between users and organization roles.
- `departments`: organizational structure for reporting and document access.
- `document_permissions`: explicit ACL grants or denies for a document.
- `document_chunks`: extracted chunk content with vector metadata linkage.
- `ingestion_jobs`: asynchronous processing state.
- `messages`: chat records and user/assistant turns.
- `citations`: verifiable links from generated answers to document evidence.
- `usage_records`: model and tracking records.

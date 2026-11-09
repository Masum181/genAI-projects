# OpenAPI Design Guidelines

## 1. Naming conventions
- Use nouns for resource paths: `/documents`, `/conversations`, `/feedback`.
- Use lowercase kebab-case for route segments when names must be compound.
- Use `GET` for reads, `POST` for creates, `PATCH` for partial updates, `DELETE` for deletion.

## 2. Response conventions
- All responses use JSON with a top-level `success` boolean and a request ID.
- Errors use a consistent envelope with `code`, `message`, and optional `details`.

## 3. Validation conventions
- Validate all request parameters against the schema and application-level tenant rules.
- Reject ambiguous ids and invalid enums before any data access.

## 4. Security conventions
- Require auth for all non-public endpoints.
- Enforce permission checks before state mutation.
- Never trust client-supplied tenant identifiers or document IDs.

## 5. Versioning
- Keep the API version in the URI path.
- Avoid breaking changes without a new version introduction.

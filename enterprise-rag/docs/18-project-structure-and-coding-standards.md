# 18. Project Structure and Coding Standards

## 1. Proposed directory structure
```text
app/
  api/v1/              # versioned HTTP routes
  auth/                # identity and authorization
  core/                # settings, policies, and shared concerns
  database/            # async SQLAlchemy engine and declarative base
  models/               # relational persistence model boundaries
  schemas/              # Pydantic contract boundaries
  repositories/         # PostgreSQL query boundaries
  services/             # application use cases
  rag/                  # replaceable extraction and RAG components
  integrations/         # Qdrant, object storage, Redis, and LLM adapters
  workers/              # Celery application and task boundaries
  middleware/           # request and tenant context
  monitoring/           # logs, metrics, and tracing
  tests/
alembic/                # database migration configuration and revisions
tests/                  # project-level API smoke tests
docs/
Dockerfile
docker-compose.yml
.env.example
pyproject.toml
requirements.txt
```

The source tree is a foundation, not a feature-complete application. Modules
without behavior yet document their intended boundary; domain models, routes,
provider adapters, and background workflows are added with their corresponding
business requirements rather than represented by placeholder implementations.

## 2. Module responsibilities
- `api`: HTTP and SSE endpoints.
- `core`: configuration, security, and shared utilities.
- `database`: async database engine, sessions, and declarative metadata.
- `models`: SQLAlchemy persistence model boundaries.
- `schemas`: request/response validation models.
- `services`: domain behavior and orchestrations.
- `repositories`: database access and query logic.
- `integrations`: isolated external provider clients and adapters.
- `rag`: extraction, retrieval, reranking, and prompt orchestration.
- `workers`: Celery tasks.
- `middleware`: request correlation and tenant context.
- `monitoring`: logger and metrics integration.

## 3. Python standards
- Python 3.11+
- Type annotations for all public functions.
- Pydantic models for validation.
- Avoid implicit `Any` where possible.
- Centralized error handling.

## 4. SQLAlchemy conventions
- Use SQLAlchemy 2.x style queries.
- Keep session scopes limited to request or task boundaries.
- Persist all tenant state explicitly and validate it at service boundaries.

## 5. Testing conventions
- Unit tests for services and permission logic.
- Integration tests for database and Qdrant interactions.
- Security tests for cross-tenant access and injection prevention.
- Retrieval evaluation tests for benchmark datasets.

## 6. Documentation standards
- Each major module has a clear responsibility statement.
- API and schema changes require doc updates.
- Keep ADRs and requirements traceability current.

## 7. Related documents
- [02-software-requirements-specification.md](./02-software-requirements-specification.md)
- [19-implementation-roadmap.md](./19-implementation-roadmap.md)
- [20-risks-and-architecture-decisions.md](./20-risks-and-architecture-decisions.md)

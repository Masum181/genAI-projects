# Enterprise Knowledge Intelligence Platform

This repository is the Python 3.11+ foundation for a multi-tenant RAG SaaS
application. It uses a modular monolith with clear API, service, repository,
integration, and RAG boundaries. Document uploads are stored and processed by a
Celery ingestion worker that indexes extracted chunks in Qdrant. Retrieval and
grounded chat workflows are still under development.

## Architecture map

- `app/api`: FastAPI routing and HTTP concerns.
- `app/auth`, `app/core`: identity, authorization, configuration, and shared policy.
- `app/database`, `app/models`, `app/schemas`: PostgreSQL foundations, ORM model
  boundaries, and Pydantic contract boundaries.
- `app/services`, `app/repositories`: use-case orchestration and relational
  persistence boundaries.
- `app/rag`: supported document extraction, overlap-aware chunking, and dense
  embedding/indexing components; retrieval, reranking, and generation remain
  future work.
- `app/integrations`: Qdrant, object storage, Redis, and LLM adapter boundaries.
- `app/workers`: Celery application and background document-ingestion task.
- `app/middleware`, `app/monitoring`, `app/utils`: cross-cutting infrastructure.
- `alembic`: database migration configuration and revision directory.
- `docs`: product, architecture, security, and implementation documentation.

PostgreSQL is the source of truth for relational data. Qdrant is reserved for
vectors and authorized retrieval metadata. Tenant/document authorization must be
resolved by the server before retrieval; the retrieval protocol requires an
explicit scope.

## Local setup

Requires Python 3.11+ and Docker Compose.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,ai]"
Copy-Item .env.example .env
```

Edit `.env` and replace local placeholder values before starting the services.
The Compose defaults are for local development only and are not production
credentials.

## Start infrastructure and application

Start PostgreSQL, Qdrant, Redis, and MinIO:

```powershell
docker compose up -d postgres qdrant redis minio
```

Run the API from the project directory:

```powershell
uvicorn app.main:app --reload
```

The liveness endpoint is `http://localhost:8000/health`; the versioned API
prefix is `/api/v1`. The liveness endpoint does not assert that external
dependencies are available.

Run a Celery worker in another terminal:

```powershell
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

To run the API and worker in containers with the infrastructure:

```powershell
docker compose up --build
```

The Alembic environment is configured, but no application tables or migrations
exist yet. The initial migration should be added after relational models are
defined.

## Validation

```powershell
python -m compileall -q app alembic
pytest
```

The `ai` extra provides the configured Sentence Transformers embedding model and
hosted-provider SDKs. It is required for document indexing and is installed by the
Docker image:

```powershell
python -m pip install -e ".[ai]"
```

## Recommended next steps

1. Define tenant-owned SQLAlchemy models, constraints, and initial Alembic migration.
2. Implement authentication and server-side tenant/role/document authorization.
3. Add repository and service use cases with cross-tenant access tests.
4. Add integration tests for ingestion across PostgreSQL, MinIO, Redis, and Qdrant.
5. Complete authorized Qdrant retrieval and enforce document ACL filters before ranking.
6. Implement provider adapters, citation validation, and end-to-end RAG evaluation.

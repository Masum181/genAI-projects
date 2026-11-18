# AGENTS.md

## Repository map
- Git root is `genAI-projects`; the real Python app is in `enterprise-rag/`. Run all Python, pytest, uvicorn, alembic, and Celery commands from `enterprise-rag/` — `.env`, pytest paths, and imports are cwd-relative.
- Treat `enterprise-rag/pyproject.toml` as the canonical dependency/config source. Both root `requirements.txt` and `enterprise-rag/requirements.txt` are identical mirrors; keep them aligned if you edit dependencies.
- `enterprise-rag/docs/` is a large design/spec set, not an implementation guide. `enterprise-rag/README.md` is stale in places (for example it says models/workflows do not exist). Verify spec claims against `app/` and tests.
- `qdrant_checking.py` and `rag_query.py` at the git root are standalone prototype CLIs, not part of the FastAPI app or test suite. App RAG code lives under `enterprise-rag/app/rag/` and `app/services/`.
- Much of `app/rag/` is intentionally empty stubs. Chat currently returns `insufficient_evidence`, or HTTP 503 when indexed documents exist; retrieval/reranking/generation are not wired yet.

## Setup and validation
- Requires Python 3.11+. From `enterprise-rag/`: `python -m pip install -e ".[dev]"`.
- Use `".[dev,ai]"` for Sentence Transformers/OpenAI/Gemini; the `dev` extra omits them. The Dockerfile also installs only base deps (`pip install .`), not the `ai` extra.
- Copy `enterprise-rag/.env.example` to `enterprise-rag/.env`. Settings groups use prefixes `APP_`, `DATABASE_`, `QDRANT_`, `REDIS_`, `STORAGE_`, `EMBEDDING_`, `LLM_`.
- `.env.example` has inconsistent database values: compose overrides `DATABASE_URL` in containers, but a host-run API uses the literal `DATABASE_URL`, so make it match `POSTGRES_*` when running uvicorn locally.
- Infrastructure: `docker compose up -d postgres qdrant redis minio`.
- API: `uvicorn app.main:app --reload`; Celery worker: `celery -A app.workers.celery_app.celery_app worker --loglevel=INFO`.
- Validation: `python -m compileall -q app alembic && pytest`; lint with `ruff check .` (py311, line length 88, rules E/F/I/UP/B). There is no CI or pre-commit config.
- Focused tests: `pytest app/tests/unit/test_layering.py -q` or `pytest path/to/test_file.py::test_name`.
- Default tests mock PostgreSQL/Qdrant and do not need infrastructure; `app/tests/integration/`, `security/`, and `evaluation/` are empty.

## Architecture rules
- Layering is enforced by `app/tests/unit/test_layering.py` via AST parsing: API code must not call SQLAlchemy session methods (`add`, `commit`, `execute`, `get`, etc.) on `db`/`session`; services must not import `app.api` or execute DB operations. New query logic belongs in `app/repositories/`.
- Browser routes in `app/web.py` use the same services and auth dependencies as API routes. New API routes should use `app.api.v1.common.response` / `app.api.responses.success_response`.
- Tenant isolation is server-resolved from `Principal`; never trust a client-supplied `organization_id`. Repositories scope every query by organization and ACL filters (see `app/repositories/document_repository.py`). `Principal.is_admin` bypasses permission checks.
- Auth is a hand-rolled stdlib HS256 JWT (`app/auth/token.py`), not PyJWT. Access/refresh tokens carry `sub`/`org`; revocation uses Redis keys. API keys are also supported via `X-API-Key` and are scope-limited.
- SQLAlchemy is async 2.x style. Models are auto-imported in `app/models/__init__.py`; `app/tests/unit/test_models.py` asserts the exact 21-table set, so update it when adding/removing models. IDs use the custom UUIDv7 default in `app/models/mixins.py`; `DocumentChunk.chunk_metadata` maps to DB column `metadata`.
- Alembic is configured, but `alembic/versions/` has no migrations despite defined models. Create an initial migration before expecting a usable database schema.

## Operational gotchas
- Qdrant uses one unnamed dense vector collection (`QDRANT_COLLECTION_NAME`, default `document_chunks`), COSINE, dimension `EMBEDDING_DIMENSIONS` (default 384). Startup creates payload indexes and raises on vector-dimension mismatch; changing embedding model/dimensions requires recreating the collection.
- Uploads go to MinIO; the bucket is created lazily on the first upload. Supported extensions are `.pdf .docx .xlsx .txt .html .htm`; duplicate content hashes return HTTP 409.
- Health semantics: `/health` is liveness only; `/ready` checks PostgreSQL and Qdrant and returns 503 if either is unavailable. App startup itself checks PostgreSQL and ensures the Qdrant collection.
- `enterprise-rag/generate_docs.py` rewrites every `docs/*.md` and hardcodes `F:\project\genAI-projects\enterprise-rag`; do not run it on Linux. Edit docs directly unless intentionally fixing the generator.
- Do not commit `.env`; treat committed example credentials as local-only placeholders.

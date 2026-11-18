# Centralized Logging

The application always writes structured JSON logs to rotating files in
`enterprise-rag/logs/`. The API writes to `api.log`; Celery writes to
`worker.log`. Each file is limited to 10 MB with five backups. Docker Compose
bind-mounts this directory so the logs remain available on the host after
containers stop.

Run the API from `enterprise-rag/` to also show application logs in the terminal:

```powershell
python -m app.main --log=true
```

By default, the command writes logs to files without mirroring application logs
to the terminal. Use `--log=false` to make that explicit. Docker's own container
and Uvicorn output may still appear on the terminal independently.

## Configuration

Set these `APP_` environment variables:

- `APP_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`
- `APP_LOG_FORMAT`: `json` or `text` for both file and console output
- `APP_ENVIRONMENT`: deployment environment name
- `APP_SERVICE_NAME`: service label and log file name

Docker Compose also rotates container stdout/stderr logs with a 20 MB limit and
retains five files.

## Correlation

Each HTTP request receives an `X-Request-ID`. A valid supplied value is preserved;
otherwise the API generates a UUID. `X-Correlation-ID` is also accepted and
propagated. Both IDs are returned in response headers and included in structured
logs. The request ID is available to FastAPI handlers and repository/service calls
through logging context.

Celery tasks expose `task_id` and document/job identifiers in their logs.

## Tracing failures

- API failure: filter with the returned `request_id`.
- Document ingestion: filter with `document_id` or `task_id`.
- LLM provider: filter for `app.llm`/`app.llm.ollama` and `operation=llm.generate`.
- Database: filter for `app.database` and `DATABASE_ERROR`.
- Object storage: filter for `app.storage` and `STORAGE_ERROR`.

## Docker commands

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs --tail=200 api
docker compose logs --since=30m api
docker compose logs -f --timestamps api worker
docker compose logs api | grep '"request_id":"<request-id>"'
docker compose logs worker | grep '"document_id":"<document-id>"'
```

On Windows PowerShell, use `Select-String` in place of `grep`:

```powershell
Get-Content .\logs\api.log -Wait
Select-String -Path .\logs\api.log -Pattern '"request_id":"<request-id>"'
Get-Content .\logs\worker.log -Tail 200
```

Prompts, generated confidential content, authorization headers, cookies, API
keys, database parameters, and uploaded document contents are not logged.

# 14. Observability and Monitoring

## 1. Observability model
The platform must emit structured logs and request traces across API, retrieval, and ingestion layers. This allows debugging, evaluation, and SLA monitoring without requiring manual inspection of ad hoc logs.

## 2. Structured logging
Every request log should include:
- request_id
- organization_id
- user_id
- route
- status_code
- duration_ms
- error_code where present

## 3. Request tracing
Use OpenTelemetry spans for:
- API request lifecycle
- auth validation
- retrieval requests
- LLM generation calls
- ingestion tasks
- database operations

## 4. RAG pipeline tracing
Trace each stage:
- query normalization
- access enforcement
- dense retrieval
- sparse retrieval
- reranking
- context construction
- final generation
- citation verification

## 5. Metrics
Key metrics include:
- query latency p50/p95
- ingestion duration
- retrieval recall by query type
- token usage per model
- cost per conversation and per org
- worker queue depth and saturation
- error rate by route or job type

## 6. Langfuse and OpenTelemetry integration
- Langfuse can record runs, retrieval steps, and model calls.
- OpenTelemetry provides vendor-neutral instrumentation and trace correlation.
- Use consistent trace IDs across app, celery, and LLM calls.

## 7. Suggested alert thresholds
- API p95 latency above target threshold.
- Ingestion queue backlog beyond a set threshold.
- Error rate above 2-5% for a sustained period.
- Dead-letter queue count grows beyond a safe limit.
- Token spend exceeds daily budget thresholds.

## 8. Dashboard design
Dashboards should include:
- user activity by org
- document ingestion status
- document retrieval quality
- LLM cost and latency
- worker health
- failed jobs and dead-letter counts

## 9. Related documents
- [12-background-processing.md](./12-background-processing.md)
- [15-deployment-and-devops.md](./15-deployment-and-devops.md)
- [13-evaluation-and-testing.md](./13-evaluation-and-testing.md)

# Enterprise RAG Documentation Index

This document set describes a production-grade Enterprise Knowledge Intelligence Platform built on a modular monolithic architecture with a clear path to distributed services.

## Documentation Manifest

### Core project documentation
- [01-project-overview.md](./01-project-overview.md) — business problem, vision, scope, and success criteria.
- [02-software-requirements-specification.md](./02-software-requirements-specification.md) — functional and non-functional requirements.
- [03-roles-and-permissions.md](./03-roles-and-permissions.md) — role model, RBAC, access control and matrix.
- [04-system-architecture.md](./04-system-architecture.md) — architecture overview and diagrams.
- [05-database-design.md](./05-database-design.md) — PostgreSQL schema, ERD, DDL, indexing, and RLS guidance.
- [06-api-design.md](./06-api-design.md) — REST API contracts and examples.
- [07-document-ingestion.md](./07-document-ingestion.md) — ingestion pipeline, chunking, embedding, and lifecycle.
- [08-rag-pipeline.md](./08-rag-pipeline.md) — hybrid retrieval, reranking, prompt construction and grounded QA.
- [09-vector-database-design.md](./09-vector-database-design.md) — Qdrant collections, payloads, and tenant isolation.
- [10-security-and-privacy.md](./10-security-and-privacy.md) — authentication, authorization, privacy, and threat model.
- [11-llm-and-prompt-design.md](./11-llm-and-prompt-design.md) — prompt engineering and LLM abstraction.
- [12-background-processing.md](./12-background-processing.md) — Celery/Redis architecture and async jobs.
- [13-evaluation-and-testing.md](./13-evaluation-and-testing.md) — retrieval and generation evaluation strategy.
- [14-observability-and-monitoring.md](./14-observability-and-monitoring.md) — logging, tracing, metrics, dashboards, and alerts.
- [15-deployment-and-devops.md](./15-deployment-and-devops.md) — Docker, CI/CD, environment config, backups, and production architecture.
- [16-frontend-ux-specification.md](./16-frontend-ux-specification.md) — UI specification for admin, employee, and document workflows.
- [17-business-workflows.md](./17-business-workflows.md) — operational business flows across organizations and documents.
- [18-project-structure-and-coding-standards.md](./18-project-structure-and-coding-standards.md) — repository structure and engineering standards.
- [19-implementation-roadmap.md](./19-implementation-roadmap.md) — phased milestone plan.
- [20-risks-and-architecture-decisions.md](./20-risks-and-architecture-decisions.md) — risk register and ADRs.
- [21-glossary-and-references.md](./21-glossary-and-references.md) — glossary and references.

### Supporting documentation
- [requirements-traceability-matrix.md](./requirements-traceability-matrix.md) — requirement-to-architecture/API/schema mapping.
- [openapi-design-guidelines.md](./openapi-design-guidelines.md) — naming and response conventions.
- [data-dictionary.md](./data-dictionary.md) — centralized entity and field definitions.
- [state-machines.md](./state-machines.md) — document and ingestion workflow state machines.
- [glossary.md](./glossary.md) — concise technical glossary.

## Reading order
1. Start with [01-project-overview.md](./01-project-overview.md) and [02-software-requirements-specification.md](./02-software-requirements-specification.md).
2. Review [03-roles-and-permissions.md](./03-roles-and-permissions.md) and [04-system-architecture.md](./04-system-architecture.md).
3. Design and validation follow with [05-database-design.md](./05-database-design.md), [06-api-design.md](./06-api-design.md), and [10-security-and-privacy.md](./10-security-and-privacy.md).
4. Operational and AI specifics follow with [07-document-ingestion.md](./07-document-ingestion.md), [08-rag-pipeline.md](./08-rag-pipeline.md), [09-vector-database-design.md](./09-vector-database-design.md), [11-llm-and-prompt-design.md](./11-llm-and-prompt-design.md), and [12-background-processing.md](./12-background-processing.md).
5. Validation and deployment conclude with [13-evaluation-and-testing.md](./13-evaluation-and-testing.md), [14-observability-and-monitoring.md](./14-observability-and-monitoring.md), [15-deployment-and-devops.md](./15-deployment-and-devops.md), [16-frontend-ux-specification.md](./16-frontend-ux-specification.md), [17-business-workflows.md](./17-business-workflows.md), [18-project-structure-and-coding-standards.md](./18-project-structure-and-coding-standards.md), [19-implementation-roadmap.md](./19-implementation-roadmap.md), and [20-risks-and-architecture-decisions.md](./20-risks-and-architecture-decisions.md).

## Document ownership and responsibilities
- Product and architecture: project sponsor, principal architect, product owner.
- Security and compliance: security engineer, privacy lead, compliance reviewer.
- Data and AI: ML engineer, RAG lead, data engineer.
- Backend and platform: backend engineer, DevOps engineer, DBA.
- UX and frontend: product designer, frontend engineer.

## Critical architectural constraints
- Tenant isolation is mandatory in app logic and database layer.
- Qdrant retrieval always applies authorized metadata filters before ranking.
- Authorization occurs before retrieval and before the LLM can see content.
- Client-supplied organization IDs are not trusted for authorization.
- Citations must originate from retrieved source records.
- Document replacement and deletion must clean up vectors.
- Ingestion must be idempotent and recoverable.
- Model provider abstraction is mandatory.
- Prompt injection defense applies to both user prompts and retrieved documents.
- Feedback cannot automatically rewrite trusted knowledge without human review.

## Consistency audit summary
The document set is intentionally organized by architecture layer, not by feature silo, to keep access control, database design, RAG behavior, and operations aligned. Each major workflow is mapped to requirements, API contracts, and data model entities. The architecture baseline assumes a modular monolith with explicit future extension points for distributed services.

## Open architectural questions
- Whether the platform will support SSO integration with SAML/OIDC in Phase 1 or Phase 2.
- Whether local LLM deployment is required for regulated environments or only optional for evaluation.
- Whether document approval workflows are mandatory or optional for enterprise rollout.
- Whether a formal data retention policy is driven by tenant contracts or default policy engine rules.
- Whether the initial frontend will remain HTMX-based or move to a richer SPA after MVP.

# Requirements Traceability Matrix

| Requirement ID | Requirement | Architecture Component | API/Endpoint | Database Entity | Milestone | Test Coverage |
|---|---|---|---|---|---|---|
| FR-AUTH-001 | Secure user authentication | Auth service | `/auth/login` | `users`, `api_keys` | Phase 2 | Unit/integration auth tests |
| FR-ORG-001 | Multi-org isolation | Organization domain | `/organizations` | `organizations`, `memberships` | Phase 2 | Cross-tenant tests |
| FR-DOC-001 | Document upload | Document service | `/documents/upload` | `documents`, `document_versions` | Phase 3 | Upload tests |
| FR-ING-002 | Async ingestion | Worker task queue | `/ingestion-jobs/{id}` | `ingestion_jobs` | Phase 4 | Worker tests |
| FR-RAG-001 | Dense retrieval | Retrieval service | `/chat` | `document_chunks` + Qdrant | Phase 5 | Retrieval eval |
| FR-RAG-003 | Hybrid retrieval | Retrieval service | `/chat` | `document_chunks` | Phase 6 | Retrieval eval |
| FR-CHAT-003 | Citation-backed answers | Chat + RAG layers | `/chat` | `messages`, `citations` | Phase 7 | answer validation |
| FR-SEC-001 | Audit logging | Governance service | `/admin/metrics` | `audit_logs` | Phase 8 | audit tests |
| FR-EVAL-001 | Retrieval evaluation | Evaluation service | internal only | `usage_records` | Phase 9 | offline benchmark tests |
| FR-MON-001 | Usage monitoring | Monitoring service | `/admin/analytics` | `usage_records` | Phase 9 | metric dashboard checks |

# 21. Glossary and Reference Documentation

## 1. Technical glossary
- RAG: Retrieval-Augmented Generation. Combines retrieval from authoritative documents with LLM generation.
- LLM: Large language model that generates answers conditioned on context.
- Embedding: vector representation of text used for semantic similarity search.
- Vector database: database designed for approximate nearest-neighbor search.
- Semantic search: retrieval by similarity of embeddings rather than exact text match.
- BM25: lexical retrieval algorithm that ranks documents by term frequency and inverse document frequency.
- Hybrid search: combination of dense and sparse retrieval.
- RRF: Reciprocal Rank Fusion, used to merge ranking lists from multiple retrieval systems.
- Reranking: reordering candidate results using a more precise model.
- Chunking: splitting documents into smaller semantic units for retrieval.
- Context window: token budget available to the LLM at one time.
- Groundedness: answer stays tied to evidence within the retrieved content.
- Hallucination: unsupported claim generated without evidence.
- Multi-tenancy: same platform serves multiple tenant organizations while separating data.
- RBAC: role-based access control.
- RLS: row-level security in PostgreSQL.
- GraphRAG: graph-aware retrieval and reasoning over document relationships.
- Agentic RAG: retrieval workflows with tool calling and dynamic orchestration.
- MCP: Model Context Protocol; standardized way for tools and context to connect to models.
- LLMOps: operational management of large language model workloads.
- Observability: ability to inspect health, traces, and metrics of a running system.

## 2. Reference links
- FastAPI: https://fastapi.tiangolo.com/
- PostgreSQL: https://www.postgresql.org/docs/
- Qdrant: https://qdrant.tech/documentation/
- LangChain: https://python.langchain.com/
- LangGraph: https://langchain-ai.github.io/langgraph/
- Celery: https://docs.celeryq.dev/
- Redis: https://redis.io/docs/
- PyMuPDF: https://pymupdf.readthedocs.io/
- OpenTelemetry: https://opentelemetry.io/docs/
- Langfuse: https://langfuse.com/
- RAGAS: https://docs.ragas.io/
- DeepEval: https://docs.confident-ai.com/

## 3. Related documents
- [08-rag-pipeline.md](./08-rag-pipeline.md)
- [09-vector-database-design.md](./09-vector-database-design.md)
- [10-security-and-privacy.md](./10-security-and-privacy.md)

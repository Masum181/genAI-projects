# RAG Technical Assessment

**Audit date:** 2026-11-12  
**Scope:** Ingestion, extraction, chunking, embeddings, vector indexing, dense/sparse/hybrid retrieval, reranking, context construction, prompting, generation, citations, streaming, evaluation, and operational behavior  
**Method:** Static review of `app/rag/`, `app/services/retrieval_service.py`, `app/services/chat_service.py`, `app/repositories/document_repository.py`, and related schemas

## 1. Capability matrix

| Capability | Status | Evidence | Assessment |
|---|---|---|---|
| Supported extraction | `COMPLIANT` | PDF, DOCX, XLSX, HTML, TXT extractors under `app/rag/` | Core formats implemented |
| OCR / scanned PDFs | `NOT_IMPLEMENTED` | No OCR dependency or fallback path | Image-only PDFs will not yield useful text |
| Chunking | `PARTIALLY_COMPLIANT` | `app/rag/chunkers/fixed_chunker.py` | Word-based 900/120 overlap, not semantic/token-targeted |
| Embeddings | `COMPLIANT` | Sentence Transformers provider, batch embedding | Single provider family only |
| Qdrant indexing | `COMPLIANT` | Deterministic UUID5 point IDs, payload metadata, batched upsert | Dense vectors only |
| Dense retrieval | `COMPLIANT` | `app/rag/retrievers/dense_retriever.py` | Tenant/document/version/deleted filters present |
| Sparse retrieval | `PARTIALLY_COMPLIANT` | PostgreSQL `to_tsvector`/`ts_rank_cd` in `document_repository.py` | Lexical fallback, not Qdrant sparse vectors/BM25 |
| Hybrid fusion | `COMPLIANT` | RRF in `app/rag/retrievers/hybrid_retriever.py` | Correct rank fusion with deduplication |
| Reranking | `PARTIALLY_COMPLIANT` | Cross-encoder reranker | No confidence threshold or deterministic low-evidence path |
| Context selection | `PARTIALLY_COMPLIANT` | Top reranked chunks under a configured character/word budget | No compression or section-aware assembly |
| Prompt injection isolation | `COMPLIANT` | `app/rag/prompts/rag_prompt.py` | Evidence separated from instructions; refusal rules present |
| Structured generation | `COMPLIANT` | Pydantic answer schema + provider JSON mode | Provider output validated before persistence |
| Citation verification | `PARTIALLY_COMPLIANT` | IDs checked against supplied evidence; excerpts from DB chunks | Not full factual grounding; unsupported claims can remain |
| True streaming | `NOT_IMPLEMENTED` | `app/api/v1/chat.py:63-91` | SSE splits a completed answer into 80-character events |
| Usage accounting | `PARTIALLY_COMPLIANT` | `app/services/chat_service.py:160-171` | Estimated from character counts; chunk counts are words |
| Evaluation | `NOT_IMPLEMENTED` | No evaluation suite/dataset | No retrieval/generation metrics |
| RAG observability | `NOT_IMPLEMENTED` | No stage tracing/metrics | Failures and latency by stage are invisible |

## 2. Ingestion and chunking assessment

### 2.1 Extraction

- Extractors cover PDF, DOCX, XLSX, HTML, and plain text.
- No OCR fallback for image-only PDFs or scanned attachments.
- No MIME/magic-byte validation; validation is extension and size based (`app/utils/file_validation.py`).
- No malware scanning or quarantine before extraction.
- DOCX/XLSX parsing carries archive-expansion risk because there is no compressed-size/entry-count guard.

### 2.2 Chunking

- `FixedChunker` uses `chunk_words=900`, `overlap_words=120`, splitting on whitespace with source offsets.
- `token_count` is set to `end - start`, i.e., a word count, not a model-token count.
- There is no tokenizer-aware splitting, heading/section-aware chunking, table-aware handling, or semantic boundary detection.
- Page and section metadata are preserved where extractors provide them.
- A 900-word chunk can exceed the embedding model’s token window for some content, depending on token density; there is no guard against that.

**Impact:** Retrieval quality is sensitive to document structure and vocabulary. Long tables/policies may be split poorly; exact-token budgeting is inaccurate.

## 3. Retrieval assessment

### 3.1 Authorization before retrieval

The flow is correct in principle:

1. `authorized_indexed_versions` resolves the principal’s readable, current, indexed document/version pairs.
2. A `RetrievalScope` is built from those IDs.
3. Dense search filters Qdrant by organization, document, version, and `is_deleted`.
4. Sparse search applies the same tenant/ACL filters in PostgreSQL.
5. Fused candidates are re-verified against PostgreSQL before reranking.

This is a strong security-oriented design. Remaining risks are in policy scope (document management/ACL authority), not in the retrieval filter itself.

### 3.2 Dense retrieval

- Uses the configured embedding provider and a single unnamed Qdrant dense collection.
- Validates query embedding dimension against configured dimensions.
- Uses `candidate_limit` (default 40) with cosine distance.
- Pulls payload text rather than vectors.
- If Qdrant is unavailable, the exception is not mapped in `chat_service`; the request can fail with an unhandled 500.

### 3.3 Sparse retrieval

- Implemented with PostgreSQL `to_tsvector('simple', content)` and `plainto_tsquery('simple', query)`.
- This supports lexical matching but is not BM25 and is not stored in Qdrant.
- It can be slower and less scalable than a vector-native sparse index for large corpora.
- If the sparse query fails, there is no dense-only fallback despite the design document describing one.

### 3.4 Hybrid fusion

- RRF uses `rank_constant=60` and deduplicates per ranking.
- Fusion scores replace raw provider scores, which is appropriate for combining incomparable score scales.
- No weighting between dense/sparse rankings is configurable.

### 3.5 Reranking

- Cross-encoder reranks fused candidates.
- There is no score threshold, margin check, or “low confidence” branch.
- Even weak candidates are passed to generation if any candidates exist.
- The reranker model is lazily loaded; first-query latency may be high and there is no warm-up or timeout policy.

### 3.6 Failure behavior

| Failure | Current behavior | Expected behavior |
|---|---|---|
| Embedding provider unavailable | Mapped to HTTP 503 in chat service | Correct |
| Qdrant unavailable | Unhandled exception path | Controlled 503/degraded response |
| Sparse/PostgreSQL FTS failure | Unhandled exception path | Dense fallback or controlled degradation |
| Reranker model failure | Unhandled exception path | Fallback to fused ranking or controlled 503 |
| No authorized documents | Returns empty evidence, answer `insufficient_evidence` | Correct |
| No fused candidates | Returns empty evidence | Correct |

## 4. Context and prompt assessment

### 4.1 Context selection

- Evidence is selected from reranked results up to `result_limit` (default 8).
- The prompt builder enforces `context_token_limit` (default 6000) using available `token_count`, which is actually a word count.
- No compression, deduplication of near-identical passages, or section-aware assembly is implemented.
- Evidence metadata includes document title, page, section, chunk ID, and version ID.

### 4.2 Prompt injection defenses

Present:

- System instructions explicitly treat retrieved excerpts as evidence, not instructions.
- Evidence is delimited/structured separately from the user question.
- The system prompt requires answering only from evidence and refusing when insufficient.
- Output is schema-validated; citation IDs are checked against supplied evidence.

Limits:

- The model is still an LLM; a sufficiently adversarial document may influence wording within the evidence scope.
- Citation ID validation proves the citation points to supplied evidence, not that the cited excerpt supports every claim.
- No content sanitization or instruction-pattern stripping is performed on retrieved text.

## 5. Generation and citation assessment

### 5.1 Providers

- Ollama, OpenAI, and Gemini adapters are implemented behind a common protocol.
- Ollama uses `urllib` with JSON output and a timeout.
- OpenAI uses the async SDK with JSON object mode, retry/timeout configuration.
- Gemini uses the Google GenAI SDK with JSON MIME type and system instruction.
- Provider selection is cached via `lru_cache`; shutdown closes the cached generator.
- `model_configurations` is not consulted; model selection is global configuration only.

### 5.2 Structured output

- `GeneratedAnswer` uses a Pydantic contract with `status`, `answer`, `citation_ids`, and `confidence`.
- Invalid JSON/schema produces controlled failure behavior.
- `answered` responses without valid citations are downgraded to `insufficient_evidence`.
- Non-`answered` responses have citations cleared.

### 5.3 Citation verification

- Citation records are built from the actual DB/retrieved chunk metadata, not from model-supplied titles.
- IDs must exist in the prompt’s source set.
- Excerpts are taken from the retrieved chunk.
- This is good traceability, but not groundedness verification: a model can cite a real chunk that does not actually support its claim.

### 5.4 Streaming

- Both `/chat` with `stream=true` and `/chat/stream` call `answer_from_available_sources` first.
- The SSE generator then slices the completed answer into 80-character “token” events.
- This preserves the event shape but provides none of the latency benefits of real streaming.
- The answer, citations, and message IDs are already persisted before streaming begins.

## 6. Data quality and consistency risks

1. **Word-based token accounting** distorts context budgeting and usage analytics.
2. **No chunk overlap policy based on structure** can split headings/tables from their content.
3. **No embedding model reindex workflow** if the model/dimension changes; Qdrant dimension mismatch fails startup, but there is no re-embedding task.
4. **No stale-vector sweep** for documents/versions deleted outside the API path or for failed cleanup.
5. **No retrieval evaluation** means ranking changes cannot be validated.
6. **No query rewrite** limits recall for abbreviations and policy phrasing.
7. **No reranker threshold** increases the chance of generating from irrelevant evidence.

## 7. Recommended improvements

### High priority

1. Add retrieval/reranker failure mapping and dense-only or empty-evidence fallbacks.
2. Add a reranker confidence threshold and deterministic insufficient-evidence branch.
3. Replace character/word heuristics with a real tokenizer and provider-reported usage.
4. Add evaluation datasets and CI metrics (Recall@K, Precision@K, MRR, NDCG, citation accuracy, groundedness).
5. Implement OCR for scanned PDFs if the product requires them.
6. Add malware scanning/quarantine before extraction.

### Medium priority

7. Implement structure-aware/token-aware chunking with table/heading preservation.
8. Add query normalization/rewrite and routing.
9. Add context compression and near-duplicate suppression.
10. Align sparse retrieval with the documented Qdrant sparse-vector model or document the PostgreSQL choice.
11. Implement true provider streaming.
12. Warm the reranker and enforce timeouts.
13. Add RAG-stage tracing and metrics.

## 8. RAG verdict

**Partially compliant with the documented RAG design.** The security-critical retrieval path, hybrid fusion, reranking, grounded prompting, structured output, and citation traceability are implemented. Quality assurance, streaming, confidence handling, token accounting, OCR, and evaluation are not.

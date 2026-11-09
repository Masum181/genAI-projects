# 13. RAG Evaluation and Testing Strategy

## 1. Testing philosophy
The platform must be evaluated across three dimensions: retrieval quality, answer generation quality, and system reliability. Evaluation must include offline metrics, online monitoring, and security-focused tests.

## 2. Retrieval evaluation metrics
- Recall@K
- Precision@K
- Mean Reciprocal Rank (MRR)
- NDCG
- Coverage of authorized documents only

## 3. Generation evaluation metrics
- Faithfulness: answer grounded in evidence.
- Answer relevance: answer addresses the user question.
- Context relevance: chosen context is supportive and specific.
- Citation accuracy: citations match retrieved evidence.
- Groundedness: response does not stray beyond evidence.

## 4. System evaluation metrics
- Query latency
- Ingestion throughput
- Cost per query
- Error rate
- Worker success rate
- Document processing completion time

## 5. Test dataset format
```json
{
  "question": "What is the travel reimbursement cap?",
  "answer": "The reimbursement cap is $1,500 per trip.",
  "ground_truth_documents": ["travel-policy.pdf"],
  "golden_citation": {
    "document_id": "doc_123",
    "page": 14
  }
}
```

## 6. Golden dataset creation
- Curate a representative enterprise knowledge set by department.
- Label documents with expected passages and answers.
- Include edge cases such as ambiguous policy wording and insufficient evidence.

## 7. Offline evaluation
- Run retrieval and answer generation against benchmark documents.
- Capture metrics and compare against a baseline.
- Maintain a regression suite for major model or retrieval changes.

## 8. Online evaluation
- Monitor user feedback, answer scores, and citation accuracy in production-like environments.
- Capture average thumbs-up and thumbs-down rates by workflow and department.

## 9. Security evaluation
- Cross-tenant access tests with mixed permissions.
- Prompt injection tests using malicious or adversarial documents.
- Document deletion and access revocation tests.

## 10. Human evaluation
- Knowledge managers review sampled outputs.
- Evaluate relevance, safety, and whether the answer is useful for the business task.

## 11. LLM-as-a-judge limitations
LLM-based judging is useful but should not replace expert review. It can rate relevance but may also inherit model bias and blind spots. Human review remains necessary for enterprise rollout.

## 12. Evaluation report template
```md
# Evaluation Report
- Dataset: <name>
- Date: <date>
- Model: <model>
- Retrieval: <method>
- Metrics: recall, MRR, groundedness, latency
- Failures: <top issues>
- Recommendation: <next action>
```

## 13. Related documents
- [08-rag-pipeline.md](./08-rag-pipeline.md)
- [14-observability-and-monitoring.md](./14-observability-and-monitoring.md)
- [19-implementation-roadmap.md](./19-implementation-roadmap.md)

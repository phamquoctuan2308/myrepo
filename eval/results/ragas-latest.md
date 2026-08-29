# RAGAS Evaluation Evidence

- Run at: `2026-08-26T07:39:29.349755+00:00`
- Source revision: `8871730e699eae55dd9d814a02dcf87efb36906a` (dirty working tree)
- Dataset: `eval\ragas\conversation_summary_cases.jsonl` (5 cases)
- Application model: `openai/gpt-5.6-luna`
- Evaluator: `openrouter/openai/gpt-5.6-luna`
- Embeddings: `openai/text-embedding-3-small`
- Answer relevancy prompt: `vietnamese-summary-v1`
- Rerun scope: partial; cases `summary-release-001`, `summary-calendar-004`, `summary-privacy-005`; metrics `answer_relevancy` (other scores retained from the baseline report)
- Release gate: **PASS**

| Metric | Score | Gate | Status |
|---|---:|---:|---|
| `faithfulness` | 1.000 | >= 0.70 | PASS |
| `answer_relevancy` | 0.879 | >= 0.70 | PASS |
| `context_precision` | 0.844 | >= 0.60 | PASS |
| `context_recall` | 1.000 | >= 0.60 | PASS |

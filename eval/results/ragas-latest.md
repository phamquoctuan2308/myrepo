# RAGAS Evaluation Evidence

- Run at: `2026-08-25T13:23:36.192249+00:00`
- Dataset: `eval\ragas\conversation_summary_cases.jsonl` (5 cases)
- Application model: `openai/gpt-5.6-luna`
- Evaluator: `openrouter/openai/gpt-5.6-luna`
- Embeddings: `openai/text-embedding-3-small`
- Release gate: **FAIL**

| Metric | Score | Gate | Status |
|---|---:|---:|---|
| `faithfulness` | 0.550 | >= 0.70 | FAIL |
| `answer_relevancy` | 0.428 | >= 0.70 | FAIL |
| `context_precision` | 0.528 | >= 0.60 | FAIL |
| `context_recall` | 1.000 | >= 0.60 | PASS |

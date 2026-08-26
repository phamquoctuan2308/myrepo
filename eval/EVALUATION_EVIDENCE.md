# Evaluation Evidence — Orbit

Generated at `2026-08-26T07:48:37.633527+00:00` from source revision `8871730`
with uncommitted evaluation changes.

This report never converts missing evidence into a passing score. `PENDING` means the runner or
protocol exists but no current result artifact is available.

## 1. Release evidence summary

| Evidence | Result | Gate | Status |
|---|---:|---:|---|
| Automated tests | 416/417 passed, 1 skipped | No failures/errors | PASS |
| Source coverage | 67.9% | >=60% | PASS |
| Formal Agent acceptance | 100.0% case pass | Dataset gates | PASS |
| Task title F1 | 91.9% | >=70% | PASS |
| Deadline accuracy | 82.1% | >=70% | PASS |
| RAGAS grounding | 100.0% faithfulness | All RAGAS gates | PASS |
| API latency P95 | Pending | Configured runner gate | PENDING |
| User feedback | Pending | >=5 participants | PENDING |

## 2. Current measured AI quality

- Formal acceptance: `2026-08-25T14:29:05.602046+00:00` using
  `openai/gpt-5.6-luna`.
- Task extraction: `37` cases; title precision
  `85.0%`, recall
  `100.0%`, F1 `91.9%`.
- Missing or failed gates remain release risks even when deterministic unit tests pass.

## 3. Reproducible commands

```powershell
python scripts/run_coverage.py
python scripts/benchmark_api_latency.py --base-url http://127.0.0.1:8000 --endpoint /health
python scripts/eval_user_agent.py
python scripts/eval_extract_tasks.py
python scripts/eval_ragas.py
python scripts/summarize_user_feedback.py
python scripts/generate_evaluation_evidence.py
```

## 4. Traceability and evidence locations

- Requirement-to-test-to-code map: [`TRACEABILITY_MATRIX.md`](TRACEABILITY_MATRIX.md)
- Manual scenarios: [`../MANUAL_TEST_CASES.md`](../MANUAL_TEST_CASES.md)
- Screenshot/video evidence: [`../Deliverables/evidence/`](../Deliverables/evidence/)
- Formal acceptance: [`results/agent_acceptance_latest.md`](results/agent_acceptance_latest.md)
- Evaluation protocols and commands: [`README.md`](README.md)

## 5. Evidence still requiring human/external execution

- RAGAS and formal Agent evaluation require real model credentials and consume quota.
- User satisfaction requires real anonymized participants; no synthetic rating is accepted.
- Latency must be measured against the actual target environment and recorded with its URL/model.
- Coverage/JUnit artifacts must be regenerated after material source changes.

# User Agent Acceptance Evaluation

- Dataset: `orbit-user-agent-acceptance` v`1.1.0`
- Provider/model: `openrouter` / `openai/gpt-4.1-mini`
- Run at: `2026-08-29T07:44:45.665851+00:00`
- Database: isolated PostgreSQL `orbit_agent_eval_test`
- Release gate: **NOT EVALUATED (partial run)**

## Metrics

| Metric | Result |
|---|---:|
| `case_pass_rate` | 100.0% |
| `tool_routing_accuracy` | 100.0% |
| `task_precision` | N/A |
| `task_recall` | N/A |
| `task_f1` | N/A |
| `task_due_accuracy` | N/A |
| `task_priority_accuracy` | N/A |
| `required_fact_check_pass_rate` | N/A |
| `required_fact_recall` | N/A |
| `forbidden_claim_rate` | 0.0% |
| `memory_retrieval_accuracy` | N/A |
| `memory_isolation_pass_rate` | N/A |
| `expired_memory_rejection_rate` | N/A |
| `hitl_preconfirmation_side_effect_rate` | 0.0% |
| `latency_mean_ms` | 4268.302 |
| `latency_p50_ms` | 3776.430 |
| `latency_p95_ms` | 5716.510 |
| `llm_judge_mean_score` | N/A |
| `unsupported_claim_rate` | N/A |
| `prompt_tokens` | 32880 |
| `completion_tokens` | 319 |
| `total_tokens` | 33199 |
| `llm_request_count` | 8 |
| `estimated_cost_usd` | 0.013662 |
| `unpriced_tokens` | 0 |

## Cases

| Case | Capability | Status | Score | Latency | Tools |
|---|---|---:|---:|---:|---|
| `ROUTE-03` | human_in_the_loop | PASS | 100.0% | 5717 ms | check_request_policy, create_reminder |
| `HITL-01` | human_in_the_loop | PASS | 100.0% | 3688 ms | check_request_policy, create_reminder |
| `HITL-02` | human_in_the_loop | PASS | 100.0% | 3776 ms | check_request_policy, create_reminder |
| `HITL-03` | human_in_the_loop | PASS | 100.0% | 3892 ms | check_request_policy, create_reminder |
## Interpretation limits

- Task, routing, isolation, expiry and HITL metrics are deterministic.
- Free-form summary quality uses lexical checks plus an optional LLM judge; review failures manually.
- User satisfaction and production drift require repeated human evaluation and are not inferred from this run.

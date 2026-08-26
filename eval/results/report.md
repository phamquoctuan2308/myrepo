# Evaluation Report — 2026-08-21

## Executive summary

Orbit's core product flows are implemented: authenticated user/admin applications, AI-assisted
conversation analysis, task/reminder/calendar workflows with confirmation, proactive suggestions,
and persistent agent memory. The current quality evidence is strongest for agent-memory lifecycle
and safety contracts; task extraction has a real-model benchmark and now has concrete error cases
to improve.

## Measured results

| Metric | Result | Status |
|---|---:|---|
| Agent quality harness | 17 / 17 passed | Pass |
| Task extraction title precision | 85.0% | Pass |
| Task extraction title recall | 100.0% | Pass |
| Task extraction title F1 | 91.9% | Pass (threshold 70%) |
| Deadline/date accuracy | 82.1% (23 / 28) | Pass (threshold 70%) |
| Provider evaluation failures | 0 / 37 cases | Pass |
| Full regression suite | 381 / 381 passed | Pass |
| Source coverage | 80% | Pass |
| Agent latency p50/p95 | Not yet measured | Pending |
| User satisfaction | Not yet measured | Pending |

The task-extraction benchmark used 37 versioned Vietnamese/English synthetic and team-curated
cases on 2026-08-21 (`Asia/Ho_Chi_Minh`) with Groq `openai/gpt-oss-20b`. The machine-readable
result is `task-extraction-latest.json` in this directory.

## What the automated harness protects

- Short-term context retains recent turns while trimming overflow.
- A short follow-up can resolve the previous clarification in the same thread.
- Long-term user memory recalls across separate assistant threads without crossing users.
- Expired, pending, revoked and superseded notes do not enter recall.
- Hard illegal requests and prompt-injection attempts are blocked before semantic classification.
- A safe but ambiguous request produces one concrete clarification question.
- Heartbeat compaction is idempotent, retains provenance/timestamps and rejects injected durable notes.
- Task scoring counts false positives, false negatives and date errors separately.

## Current quality risks / next actions

1. Reduce task-extraction false positives in rhetorical questions, FYI/past-completion statements,
   small talk, and long chats with unrelated statements.
2. Improve date resolution for multi-speaker attribution, `next week`, revised deadlines and
   Vietnamese weekday phrases.
3. Enforce the measured 80% coverage as a CI gate and increase coverage for the low-tested
   authentication, chat-route and memory-tool error paths.
4. Add a latency runner with p50/p95 and provider/model metadata.
5. Collect structured user acceptance feedback for task/calendar/memory flows.

The full regression and coverage run was executed on 2026-08-21 against an isolated disposable
PostgreSQL database: `381 passed` in 6m57s. It emitted deprecation warnings from the test client
and pytest-asyncio, plus a deliberately short test JWT secret warning; no test failed.

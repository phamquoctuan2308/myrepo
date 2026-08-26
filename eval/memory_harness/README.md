# Memory evaluation harness

This directory holds synthetic, versioned retrieval cases. It is deliberately separate from the
general conversation golden dataset: a memory case declares the records available to a user, the
query, the records that must be recalled, and records that must never be returned.

`cases.jsonl` is UTF-8 JSON Lines. Each case has:

- `case_id`: stable identifier used in CI failures and reports;
- `kind`: currently `retrieval`;
- `records`: synthetic records with `owner`, status and optional expiry;
- `expected_ids` / `forbidden_ids`: positive recall and non-leakage contract;
- `minimum_recall`: required fraction of expected IDs returned.

Run the complete deterministic harness against the dedicated disposable test database:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:<password>@localhost:5432/orbit_test"
python scripts/run_memory_harness.py
```

The runner writes a JUnit report to `eval/results/memory-harness.junit.xml` for CI systems. It
fails before running pytest unless the database name explicitly ends in `_test`, `_tests`, or
`_harness`, and it refuses a URL equal to `DATABASE_URL`.

The runner never uses `DATABASE_URL` from a development or production environment. Do not point
`TEST_DATABASE_URL` at Supabase or any shared database: the global fixture recreates its schema.

The runner executes the complete agent-quality harness: short-/long-term memory continuity,
retrieval quality, owner isolation, expiry/revocation, semantic-ranking fallback, explicit
supersession, context-budget/prompt-boundary invariants, injection-resistant durable writes,
hard-policy blocking, ambiguity clarification, task-evaluation scoring, heartbeat compaction and
maintenance/idempotency.

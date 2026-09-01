# Memory Harness - PostgreSQL

- Run: `2026-08-29T15:18:43.651370+07:00`
- Database: PostgreSQL 17.10, isolated test database `orbit_agent_eval_test` at `127.0.0.1:55432`
- Result: **17/17 PASS**, 0 failures, 0 errors, 15.017 seconds
- SQLite fixture: bypassed for this run

Repository behavior, memory lifecycle/TTL, user isolation, semantic retrieval, context budgeting, maintenance, safety routing, and task-scoring checks ran against PostgreSQL through `postgresql+asyncpg`.

The disposable local database was used because this harness creates and removes test data. No destructive harness operation was run against production.

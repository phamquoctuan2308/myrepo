# API Latency Evidence

- Run at: `2026-08-28T05:43:42.966595+00:00`
- Target: `GET http://127.0.0.1:8010/health`
- Requests: `100` after `10` warm-up requests
- Concurrency: `10`
- Success rate: `100.0%`
- Gate: **PASS** (`p95 <= 5000 ms` and 100% expected statuses)

| Metric | Result |
|---|---:|
| Min | 6.110 ms |
| Mean | 13.733 ms |
| P50 | 13.250 ms |
| P95 | 21.238 ms |
| P99 | 23.765 ms |
| Max | 24.403 ms |

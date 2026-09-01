# API Latency Evidence

- Run at: `2026-08-28T05:43:54.607599+00:00`
- Target: `GET http://127.0.0.1:8010/ready`
- Requests: `100` after `10` warm-up requests
- Concurrency: `10`
- Success rate: `100.0%`
- Gate: **PASS** (`p95 <= 5000 ms` and 100% expected statuses)

| Metric | Result |
|---|---:|
| Min | 317.242 ms |
| Mean | 953.142 ms |
| P50 | 963.389 ms |
| P95 | 1185.869 ms |
| P99 | 1344.410 ms |
| Max | 1412.458 ms |

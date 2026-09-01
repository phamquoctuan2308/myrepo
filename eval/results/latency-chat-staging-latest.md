# Staging Chat Latency and Cost

- Run: `2026-08-29T13:15:04.466Z`
- Target: `POST https://orbit-backend-xkgq.onrender.com/api/v1/chat`
- Model: `google/gemini-2.5-flash`
- Requests: **10**, sequential
- Success: **10/10**
- Streaming: **No**; TTFB is not true first-token latency.

| Metric | TTFB | Total |
|---|---:|---:|
| P50 | 1550.34 ms | 1551.483 ms |
| P95 | 4544.529 ms | 4545.144 ms |
| P99 | 6136.874 ms | 6137.444 ms |
| Max | 6534.96 ms | 6535.519 ms |

## Usage delta

- Prompt tokens: **0**
- Completion tokens: **0**
- Total tokens: **0**
- Provider requests logged: **0**
- Estimated cost: **$0.000000**
- Unpriced tokens: **0**

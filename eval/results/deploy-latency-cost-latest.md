# Deployment Latency and Cost Evidence

- Target: `https://orbit-backend-xkgq.onrender.com/api/v1/chat`
- Effective daily token budget: `300000`

| Purpose | Success | P50 | P95 | Avg input | Avg output | Cost/call |
|---|---:|---:|---:|---:|---:|---:|
| summary | 25/25 | 1260.351 ms | 8010.157 ms | 448.0 | 50.85 | $0.00009771 |
| task_extraction | 25/25 | 1417.374 ms | 5869.951 ms | 476.0 | 94.0 | $0.00012780 |
| planner | 4/5 | 2964.055 ms | 8419.351 ms | 3905.0 | 104.75 | $0.00064860 |

Known subtotal per 1,000 messages: **$0.152487**.

This is not a full total: proactive extraction and rolling summary cannot be separated because the deployed `usage_logs` table has no purpose label.

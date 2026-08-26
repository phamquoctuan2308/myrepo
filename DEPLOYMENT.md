# Orbit deployment

The production shape is intentionally one backend process, one user SPA, and one admin SPA.
Do not scale the backend horizontally: WebSocket connections and APScheduler jobs are currently
process-local.

## Backend (Render)

1. Apply `render.yaml` and set every `sync: false` value in the Render dashboard.
2. Use a PostgreSQL `DATABASE_URL`; production configuration rejects SQLite.
3. Set `CORS_ORIGINS` to both exact Vercel origins, comma-separated and without `*`.
4. Add `RENDER_DEPLOY_HOOK_URL` as a GitHub secret and `RENDER_URL` as a GitHub variable.
5. Run the `Deploy backend` workflow once manually. Later main-branch deployments run only after CI succeeds.

Before Uvicorn starts, the container upgrades a versioned database with Alembic. A database made
by the older `create_all` startup path is stamped only after every current ORM table and column is
verified. `/health` is liveness-only; Render rollout checks use `/ready`, which also verifies the
database schema and the current Alembic revision in production.

## Frontends (Vercel)

Create two Vercel projects from the same repository:

| Project | Root directory | Dev port |
|---|---|---:|
| Orbit User | `Frontend/user` | 5173 |
| Orbit Admin | `Frontend/admin` | 5174 |

For each project, set `VITE_API_BASE_URL=https://<backend>/api/v1`. Set
`VITE_WS_BASE_URL=wss://<backend>/api/v1/ws` for the user project. Each app's `vercel.json`
preserves client-side routes on refresh.

## Release checks

- Run `ruff check src tests` and `pytest tests -q`.
- Run `npm run build` from `Frontend`.
- Verify login, a real WebSocket exchange, one AI turn, one confirmed reminder, admin usage/audit,
  and a direct refresh of a nested route.
- Confirm repeated failed login and chat bursts return HTTP 429.

Google Calendar also needs the credentials/token strategy documented in `.env.example`; do not
deploy local secret files into the image.

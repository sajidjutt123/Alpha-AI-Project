# Alpha AI

**AI Real-Estate Lead Qualification & Sales Automation Platform**

Leads arrive via **WhatsApp / SMS** → an **AI agent** converses 24/7,
extracts requirements, qualifies the lead (HOT / WARM / COLD), matches
properties from the catalogue, and hands everything to a **live agent
dashboard**. HubSpot + AI sales agent + WhatsApp automation — purpose-built
for real-estate businesses.

```
Lead → WhatsApp/SMS → Twilio → FastAPI + AI pipeline → PostgreSQL (Supabase)
                                                    → Next.js dashboard → Agent
```

## Monorepo

| Path | What |
|---|---|
| `frontend/` | Next.js 16 + TypeScript + Tailwind CSS 4 (shadcn/ui from Phase 7) |
| `backend/` | FastAPI + Python — `api/` `core/` `models/` `schemas/` `services/` `agents/` `repositories/` `workers/` |
| `database/` | `schema.sql`, `migrations/`, `seed.sql` (Phase 2) |
| `docs/` | [architecture](docs/architecture.md) · [api](docs/api.md) · [database](docs/database.md) · [deployment](docs/deployment.md) |
| `.github/workflows/` | CI: lint + type-check + tests for backend & frontend |

## Dashboard (local)

```bash
# with the stack running (see Quickstart), open http://localhost:3000/login
# dev sign-in with a seeded agent email, e.g.:
#   ahmed@alphaestates.pk      (Owner — Alpha Estates, Lahore)
#   hassan@galaxyproperties.pk (Owner — Galaxy Properties, Karachi)
```

Realtime (Phase 8): once signed in, the dashboard keeps one SSE connection
open (`GET /api/v1/realtime/stream`). New leads land on the Kanban board
and a toast/badge fires without a refresh; an open conversation streams
inbound replies and AI responses live; the bell dropdown lists the latest
30 notifications with per-agent unread state. To see it in action: open the
dashboard, then post a Twilio webhook (or run the backend webhook tests'
`inbound_form` shape) and watch the events arrive.

## Testing & security (Phase 9)

```bash
# backend: 163 tests + coverage (96%), incl. the security suite
cd backend && pytest --cov=app

# frontend: unit tests (SSE parsing / backoff)
cd frontend && npm test
```

Security posture and the full audit (findings, fixes, accepted risks,
dependency remediation) live in [docs/security-audit.md](docs/security-audit.md).

## Quickstart (local)

```bash
cp .env.example .env

# 1) Database (Postgres 16) + apply migrations & seed
docker compose up -d db
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export ADMIN_DATABASE_URL=postgresql://alpha:alpha@localhost:5432/alpha_ai
python -m app.db.migrate --seed

# 2) Backend API
uvicorn app.main:app --reload    # → http://localhost:8000/api/v1/docs

# 3) Frontend
cd ../frontend
cp .env.example .env.local
npm install
npm run dev                      # → http://localhost:3000
```

Everything also runs without Docker: with no `TEST_DATABASE_URL` set, the
test suite auto-provisions an embedded PostgreSQL (via `pgserver`).

## Development commands

| Area | Command |
|---|---|
| Backend tests | `cd backend && pytest` |
| Backend lint | `cd backend && ruff check . && ruff format --check .` |
| Backend types | `cd backend && mypy app` |
| Frontend lint | `cd frontend && npm run lint` |
| Frontend build | `cd frontend && npm run build` |

CI runs the same commands on every push/PR (`.github/workflows/ci.yml`).

## Roadmap — 11 phases

| # | Phase | Status |
|---|---|---|
| 1 | Architecture & scaffolding | ✅ **done** |
| 2 | Database + Auth (schema, RLS multi-tenant, migrations, seed) | ✅ **done** |
| 3 | FastAPI core APIs (auth middleware, leads/properties/agents/analytics) | ✅ **done** |
| 4 | Twilio webhook pipeline (signature, routing, idempotent ingest, queue seam) | ✅ **done** |
| 5 | AI engine (intent, extraction, scoring, handoff, telemetry) | ✅ **done** |
| 6 | Property matching + LangGraph workflow + validated tools | ✅ **done** |
| 7 | Agent dashboard (auth, KPIs, Kanban, live chat, properties) | ✅ **done** |
| 8 | Realtime & notifications (SSE event bus, live board/transcript, bell + toasts) | ✅ **done** |
| 9 | Testing + security audit (96% coverage, rate limiting, headers, CVE remediation) | ✅ **done** |
| 10 | Deployment (Vercel + Railway/Render + Supabase) | ⬜ |
| 11 | Demo + sales package | ⬜ |

## Core principles

1. **Multi-tenant from day one** — every table scoped by `organization_id`, isolated by RLS.
2. **The LLM never owns business logic** — LangGraph orchestrates; deterministic code decides.
3. **AI never touches the DB** — validated tools only, executed by the backend.
4. **Webhooks return 200 fast** — validate, store, enqueue; process async.
5. **No secrets in Git** — configure via `.env` (see `.env.example`).

## License

MIT — see [LICENSE](LICENSE).

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

## Quickstart (local)

```bash
cp .env.example .env

# 1) Database + backend (Docker)
docker compose up -d            # API → http://localhost:8000/api/v1/docs

# 2) Frontend (or run it yourself — see below)
cd frontend
cp .env.example .env.local
npm install
npm run dev                     # → http://localhost:3000
```

Run the backend without Docker:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload   # → http://localhost:8000/api/v1/docs
```

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
| 2 | Database + Auth (Supabase, RLS, multi-tenant) | ⬜ |
| 3 | FastAPI core APIs (leads, properties, agents) | ⬜ |
| 4 | Twilio webhook pipeline + seed data | ⬜ |
| 5 | AI engine (intent, extraction, scoring) | ⬜ |
| 6 | Property matching + LangGraph workflow | ⬜ |
| 7 | Agent dashboard (Kanban, conversations) | ⬜ |
| 8 | Realtime & notifications | ⬜ |
| 9 | Testing + security audit | ⬜ |
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

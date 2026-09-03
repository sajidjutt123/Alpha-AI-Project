# Architecture

## System overview

```
Customer
  |
WhatsApp / SMS
  |
Twilio ── webhook ──> FastAPI API
                       ├── Authentication & signature verification
                       ├── Webhooks (validate → store → enqueue → 200)
                       ├── AI orchestration (LangGraph pipeline)
                       └── Business logic (scoring, matching, rules)
        +----------------+----------------+
        |                |                |
    OpenAI API      PostgreSQL        Redis (optional)
                   (Supabase)         async queue
                        |
                        | Realtime
                        v
                  Next.js Dashboard ──> Real-Estate Agent
```

## Monorepo layout

| Path | Contents |
|---|---|
| `frontend/` | Next.js 16 + TypeScript + Tailwind 4 (shadcn/ui in Phase 7) |
| `backend/` | FastAPI + Python 3.11+ (`api/`, `core/`, `models/`, `schemas/`, `services/`, `agents/`, `repositories/`, `workers/`) |
| `database/` | `schema.sql`, `migrations/`, `seed.sql` (Phase 2) |
| `docs/` | Architecture, API, database, deployment docs |
| `.github/workflows/` | CI (lint + type-check + test on backend & frontend) |

## Backend layering

```
HTTP route → schema validation (Pydantic) → service → repository → database
                                          ↘ agent (LangGraph) ↗
```

- **Routes** (`app/api/routes/`) — HTTP concerns only; versioned under `/api/v1`.
- **Schemas** (`app/schemas/`) — request/response contracts.
- **Services** (`app/services/`) — business rules; the single source of truth for logic.
- **Repositories** (`app/repositories/`) — the only code that touches the DB.
- **Agents** (`app/agents/`) — AI orchestration; calls *tools* implemented by services.
- **Workers** (`app/workers/`) — background processing behind a queue abstraction.

## Key decisions

### D1 — Multi-tenant from day one
Every domain table carries `organization_id`, and Supabase Row Level Security
enforces isolation at the database layer. The first deployment serves one
company, but the data model is already SaaS-shaped (no painful rewrite later).

### D2 — The LLM never owns business logic
LangGraph orchestrates the conversation pipeline
(intent → extraction → qualification → property search → rules → response →
validation), but deterministic Python code performs scoring, matching and all
writes. The qualification model is configurable data, not prompt text.

### D3 — AI tools are validated, not trusted
The LLM emits *tool requests* (`search_properties`, `update_lead`,
`calculate_lead_score`, `request_human_agent`, `schedule_followup`). The
backend validates each request and executes it; the AI has no direct
database access. This prevents hallucinated writes.

### D4 — Webhooks acknowledge immediately
`POST /api/v1/webhooks/twilio` validates the Twilio signature, persists the
message, enqueues processing and returns `200` within milliseconds. The MVP
runs the "queue" in-process (FastAPI `BackgroundTasks`); the interface is
queue-shaped so Redis/Arq can drop in during Phase 8 without touching
webhook code.

### D5 — Local-first development
Docker Compose provides Postgres; Twilio/Supabase/OpenAI are accessed
through adapters driven by environment variables. The same code path runs
against real services in staging/production — only configuration changes.

### D6 — Frontend reaches the API through a server-side proxy
The browser calls relative paths (`/api/backend/...`); the Next.js server
rewrites them to the FastAPI service. No CORS exposure of the API, and the
backend URL stays server-side (`BACKEND_INTERNAL_URL`).

## AI pipeline (Phase 5–6 target)

```
Incoming message
 → load conversation history
 → intent detection        (BUY | SELL | RENT | GENERAL_INQUIRY | HUMAN_AGENT | UNKNOWN)
 → information extraction  (budget, location, type, bedrooms, urgency — structured JSON)
 → lead qualification      (0–100 score: budget 25, location 20, urgency 18/20,
                            requirements 15/20, engagement 10/15 → HOT ≥80 / WARM ≥50 / COLD)
 → property search tool    (validated backend query)
 → business rules          (deterministic filters & scoring)
 → response generation     (conversational, grounded in tool results)
 → validation              (Pydantic-checked before anything is persisted or sent)
 → persist + send          (messages, lead updates, ai_runs telemetry)
```

`ai_runs` records model, prompt version, token counts and latency for every
execution — the basis for cost tracking and debugging.

## Security model (implemented progressively; audited in Phase 9)

- Supabase Auth for dashboard users; RLS for organization-level isolation
- Twilio webhook signature validation on every inbound message
- Pydantic validation on every payload boundary
- Rate limiting on public endpoints
- CORS restricted to known origins
- Server-side secrets only; `.env` never committed
- Audit logs and Sentry error monitoring in production

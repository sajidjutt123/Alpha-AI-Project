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

### D7 — Tenant isolation is a database guarantee, not an application promise
The backend connects to PostgreSQL as a least-privilege role (`alpha_app`,
no BYPASSRLS) against tables with ENABLE + FORCE ROW LEVEL SECURITY. Each
request binds a transaction-local tenant context
(`app.current_organization_id`); RLS policies then confine every query to
one `organization_id`. Even buggy application code cannot mix tenants, and
pooled connections cannot leak tenant state. Migrations run separately as
the owner role. Details: [database.md](database.md).

### D8 — Webhooks ack in milliseconds; processing is queued behind a seam
The Twilio webhook authenticates by signature (never JWTs), routes the `To`
number to an organization via SECURITY DEFINER lookups, persists the
message idempotently (`MessageSid`), and enqueues an `InboundMessageJob`
before returning empty TwiML. The MVP queue is FastAPI BackgroundTasks;
the `MessageProcessor` protocol is the swap point for Redis/Arq (Phase 8+)
— webhook code never changes. The AI reply itself runs in that job through
the `ConversationAgent` seam (`app/agents/`), which Phase 5 fills with the
LangGraph pipeline; until then an `UnconfiguredAgent` logs and stays silent.

## AI pipeline (Phases 5+6 — implemented, LangGraph-orchestrated)

```
Incoming message (queued job, tenant-bound session)
 → load conversation history (windowed memory, AI_HISTORY_WINDOW)
 → intent detection        (BUY | SELL | RENT | GENERAL_INQUIRY | HUMAN_AGENT | UNKNOWN)
 → information extraction  (budget, location, type, bedrooms, urgency — strict JSON,
                            Pydantic-validated; crore/lakh converted to PKR)
 → lead qualification      (deterministic: budget 25, location 20, urgency 20,
                            requirements 20, engagement 15 → HOT ≥80 / WARM ≥50 / COLD;
                            weights & thresholds are configuration, never prompt text)
 → business rules          (FRUSTRATED or HUMAN_AGENT → deterministic handoff +
                            SYSTEM note; NEW → CONTACTED on first reply)
 → property matching       (validated tools: search_properties via ToolExecutor;
                            deterministic scoring budget 40 / location 25 /
                            type 15 / bedrooms 20 with affordability + type
                            gates; matches persisted with reasons)
 → response generation     (grounded in tool results, one question at a time,
                            never invents listings; honest no-match fallback)
 → validation              (length-bounded, schema-checked)
 → persist + send          (requirement updates, score, ai_runs telemetry per call)
```

Failure handling: provider/JSON errors log and degrade to silence — the
webhook already acked; a human or retry picks the thread up. Prompt
injections are treated as data (guard text in every prompt; the scorer only
reads structured facts). See `backend/app/agents/`.

## Realtime & notifications (Phase 8 — implemented)

```
Domain code ──defer_publish(session, org, type, payload)──▶ session.info["deferred_events"]
        │                                                      (survives the transaction;
        │                                                       publishes only on success)
        ▼
  commit → flush_deferred(session) ──▶ EventBus.publish(org_id, …)
                                           │
   per-org subscriber set: Set[asyncio.Queue]  (MAX_QUEUE=256 — drop-if-full,
   a slow SSE client can never stall a request path; KEEPALIVE=15s)
                                           │
                                           ▼
   GET /api/v1/realtime/stream  (SSE;  org-scoped fan-out per event)
```

**Event contract** (org-scoped; all payloads JSON):

| Event | Emitted when | Payload |
|---|---|---|
| `lead.created` | webhook creates a lead by phone | `lead_id, name, phone` |
| `message.created` | any message row appears (customer / AI / agent) | `lead_id, message_id, sender_type, preview≤80` |
| `lead.updated` | graph updated score/status/requirements | `lead_id, qualification_score, status` |
| `handoff.requested` | rules triggered human takeover | `lead_id` |
| `notification.created` | a persistent notification was written | `id, type, title, body, lead_id` |

**Notifications** are persistent rows (migration `006`), not just stream
events: org-scoped, typed (`NEW_LEAD` / `HOT_LEAD` / `HANDOFF`), with a
`read_by uuid[]` array giving per-agent read state without a join table
(`GET /notifications` computes `read`, `POST /notifications/read-all`
appends the caller).

**SSE over EventSource, deliberately.** The stream endpoint resolves the
caller's agent, then **rolls the pooled DB session back before returning the
`StreamingResponse`** — the generator never holds a connection. It is plain
SSE (not WebSockets) because the dashboard only needs server→client push;
the browser client is a `fetch` + `ReadableStream` reader rather than
`EventSource`, because EventSource cannot send the `Authorization: Bearer`
header and a `?token=` query param would leak the JWT into proxy logs.

**Multi-instance swap (documented, not needed for the MVP).** The
`EventBus` is in-process, so events reach only clients connected to the
instance that handled the request. When the API scales horizontally,
`EventBus.publish` becomes a `PUBLISH` to a Redis channel per organization
and `sse_generator` subscribes via `redis.asyncio` pub/sub — the publish
call sites, event contract, and client are unchanged. The deferred
publish/flush pattern already guarantees no event is emitted for a
transaction that rolled back.

Frontend wiring: one SSE connection per session
(`features/realtime/realtime-provider.tsx`) with capped exponential-backoff
reconnect; `useRealtimeEvent(type, handler)` fans out to the kanban board
(`lead.created`/`lead.updated` → debounced refetch), the transcript
(`message.created` for the open lead → live append), and the notification
bell (badge + toast + browser notification when the tab is hidden).

## Security model (Phase 9 audit complete — docs/security-audit.md)

- **Isolation:** RLS (`FORCE`) with a least-privilege role and transaction-scoped tenant GUC — isolation is a database guarantee, not an application promise (D7)
- **Auth:** Supabase Auth JWTs in production (HS256 today, RS256/JWKS seam ready); dev tokens only in development/test; interactive docs and `/auth/dev-login` hard-off in production
- **Webhook:** Twilio HMAC-SHA1 signature on every inbound message; fail-closed (503) if production lacks the token; idempotent on `MessageSid`
- **Rate limiting:** sliding window per client IP — dev-login 10/min, webhook 240/min, 429 + `Retry-After`; in-process with a documented Redis swap
- **Transport hardening:** OWASP security headers + `Cache-Control: no-store` on API paths (SSE-safe pure-ASGI middleware), 1 MiB request-body cap, CORS origin allowlist, CSP on the production dashboard
- **Validation:** Pydantic at every boundary; LLM output treated as data (validated tools, deterministic scoring) — the model never owns business logic
- **Secrets:** environment-only, `.env` never committed (`.env.example` documents every key)
- **Supply chain:** `pip-audit` / `npm audit` clean (LangChain stack upgraded to patched majors in Phase 9)
- **Residual risks:** documented with remediation windows in the audit report (R1–R4)
- **Deployed (Phase 10):** Docker images (`backend/Dockerfile` root-context with migrations, `frontend/Dockerfile` standalone), `docker-compose.prod.yml`, `render.yaml`/`railway.json`/`vercel.json`, first-org bootstrap CLI, and the runbook in [deployment.md](deployment.md); optional Sentry wiring activates with `SENTRY_DSN`

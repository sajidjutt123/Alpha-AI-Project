# Database Architecture

Platform: **PostgreSQL** (Supabase in staging/production; local Postgres via
Docker Compose — or an embedded test server in CI). Multi-tenant by
`organization_id` with **Row Level Security** enforced against the
application role.

DDL source of truth: `database/migrations/` (apply with
`python -m app.db.migrate` from `backend/`).

## Entity relationships

```
organizations 1──* agents          (agents.auth_user_id → Supabase Auth user)
organizations 1──* leads           (assigned_agent_id → agents, SET NULL)
organizations 1──* properties
leads         1──* messages        (conversation transcript)
leads         1──* lead_property_matches *──1 properties
leads         1──* ai_runs         (execution telemetry)
```

## Tables

### organizations — SaaS tenants
`id`, `name`, `slug` (unique), `created_at`

### agents — team members (credentials in Supabase Auth, never stored here)
`id`, `organization_id`, `name`, `email`, `phone`, `role` (OWNER/ADMIN/AGENT),
`auth_user_id` (unique → `auth.users.id`), `is_active`, `created_at`.
Unique: `(organization_id, email)`.

### leads — prospects and their qualification state
`id`, `organization_id`, `name`, `phone`, `email`, `status`
(NEW/CONTACTED/QUALIFIED/CONVERTED/LOST), `intent`
(BUY/SELL/RENT/GENERAL_INQUIRY/HUMAN_AGENT/UNKNOWN), `budget_min`,
`budget_max`, `preferred_location`, `property_type`, `bedrooms`,
`urgency_score` (1–10), `qualification_score` (0–100), `summary`,
`assigned_agent_id`, `created_at`, `updated_at` (trigger-maintained).
Unique: `(organization_id, phone)` — lead identity for webhook routing.
Check constraints guard budget ordering and score ranges.

### messages — conversation transcript
`id`, `lead_id`, `sender_type` (CUSTOMER/AI/AGENT/SYSTEM), `content`,
`channel` (WHATSAPP/SMS/DASHBOARD), `external_message_id` (unique — Twilio
SID, makes webhook processing idempotent), `created_at`.

### properties — listings (PKR prices, area in sq ft)
`id`, `organization_id`, `title`, `description`, `price`, `location`,
`property_type` (HOUSE/APARTMENT/PLOT/COMMERCIAL), `bedrooms`, `bathrooms`,
`area`, `availability` (AVAILABLE/RESERVED/SOLD/RENTED), `image_url`,
`created_at`.

### lead_property_matches — recommendations with explanation
`id`, `lead_id`, `property_id`, `match_score` (0–100), `reason`,
`created_at`. Unique: `(lead_id, property_id)`.

### ai_runs — every AI execution
`id`, `lead_id`, `model`, `prompt_version`, `input_tokens`, `output_tokens`,
`latency_ms`, `created_at`. Basis for cost tracking and debugging.

## Row Level Security — the multi-tenant guarantee

Two database roles (see `002_rls_roles.sql`):

| Role | Privilege | Used by |
|---|---|---|
| `alpha` (local) / Supabase owner | superuser/owner, runs DDL | migration runner, seeding |
| `alpha_app` | SELECT/INSERT/UPDATE/DELETE only, **no BYPASSRLS** | the backend, always |

Mechanics:

1. All seven tables use `ENABLE` + `FORCE ROW LEVEL SECURITY` (FORCE keeps
   even the table owner subject to policies — required on Supabase).
2. The backend opens each unit of work and binds the tenant context:
   `SELECT set_config('app.current_organization_id', '<org uuid>', true)` —
   transaction-local, so pooled connections can never leak tenant context.
3. Policies compare against `current_org_id()` (NULL when unbound → denies
   everything):
   - direct tables (`organizations`, `agents`, `leads`, `properties`):
     `organization_id = current_org_id()` for USING and WITH CHECK —
     cross-tenant reads return nothing, cross-tenant writes are rejected.
   - child tables (`messages`, `lead_property_matches`, `ai_runs`):
     EXISTS-join to their parent `leads` row's organization.

This means organization isolation holds even if application code has a bug —
the database itself refuses to mix tenants. Verified by the test suite
(`tests/test_database.py::TestTenantIsolation`).

## Auth model (Supabase Auth)

Dashboard users authenticate via Supabase Auth (JWT). `agents.auth_user_id`
links an auth user to an agent row; the backend resolves the JWT → agent →
organization, then binds the tenant GUC for that request. No passwords are
stored in application tables. Wiring lands with the API middleware (Phase 3).

## Indexes (hot paths)

- `leads (organization_id, status)` — Kanban/overview queries
- `leads (organization_id, created_at DESC)` — recent-leads feed
- `messages (lead_id, created_at)` — transcript history
- `properties (organization_id, property_type|price|location)` — catalog search
- unique indexes back webhook idempotency (`external_message_id`) and lead
  identity (`organization_id, phone`)

# Database Architecture

Platform: **PostgreSQL** (Supabase in staging/production; local Postgres via
Docker Compose in development). Multi-tenant by `organization_id` with
Row Level Security.

## Tables (schema lands in Phase 2 — `database/schema.sql`)

| Table | Purpose |
|---|---|
| `organizations` | SaaS tenants — one row per real-estate company |
| `agents` | Team members of an organization (auth via Supabase Auth) |
| `leads` | Prospects: contact info, status, budget, location, scores, assignment |
| `messages` | Full conversation transcript per lead (channel, sender, content) |
| `properties` | Listings: price, location, type, bedrooms, bathrooms, area, availability |
| `lead_property_matches` | AI recommendations with match score + reason |
| `ai_runs` | AI execution telemetry: model, prompt version, tokens, latency |

## Principles

- No god-table: conversations, qualification, and listings are separate.
- `organization_id` on every domain table; RLS policies enforce isolation.
- Credentials live in Supabase Auth — never as plain password columns.
- Enums as Postgres enum types (lead status: `NEW → CONTACTED → QUALIFIED →
  CONVERTED` + terminal states).
- Timestamps in `UTC` (`timestamptz`), `created_at`/`updated_at` everywhere.
- Indexes on hot paths (phone lookups, org+status filters) — Phase 9 tuning.

Detailed DDL, migrations, and RLS policies are delivered with Phase 2.

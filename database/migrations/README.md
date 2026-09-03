# Database Migrations

Sequential, hand-reviewable SQL migrations applied in order. Application is
tracked per-file in the `schema_migrations` table — each migration runs
exactly once.

## Files

| File | Contents |
|---|---|
| `001_initial_schema.sql` | Enums, 7 tables (multi-tenant), triggers, indexes, checks |
| `002_rls_roles.sql` | `alpha_app` runtime role, grants, RLS enable + FORCE, isolation policies |
| `../seed.sql` | Dev/demo data (2 orgs, PKR listings, leads, conversations) — not a migration |

## Applying

From `backend/` (requires `ADMIN_DATABASE_URL`, see root `.env.example`):

```bash
python -m app.db.migrate          # apply pending migrations
python -m app.db.migrate --seed   # additionally apply dev seed data
```

Against docker-compose Postgres:

```bash
docker compose up -d db
cd backend
source .venv/bin/activate
export ADMIN_DATABASE_URL=postgresql://alpha:alpha@localhost:5432/alpha_ai
python -m app.db.migrate --seed
```

## Conventions

- Naming: `NNN_short_description.sql`; never edit an applied migration —
  add a new one.
- `002` contains the literal `__APP_ROLE_PASSWORD__`, substituted by the
  runner from `APP_DB_PASSWORD` (charset `[A-Za-z0-9_-]` enforced).
- Never use the admin role at runtime — the backend connects as `alpha_app`
  and is confined by Row Level Security.

## Supabase (production)

The same migrations apply on Supabase: run them in the SQL editor or via
`psql` with the project's connection string as `ADMIN_DATABASE_URL`. FORCE
ROW LEVEL SECURITY keeps the table owner subject to the policies.

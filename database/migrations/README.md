# Database Migrations

Sequential, hand-reviewable SQL migrations applied in order.

Naming: `NNN_short_description.sql` (e.g. `001_initial_schema.sql`).

Apply order is tracked in `schema_migrations` (Phase 2 wires the runner —
`psql`, Supabase CLI, or alembic; the choice is finalized then).

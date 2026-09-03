"""Data-access layer (Phase 3).

Repositories are the only code that talks to the database. Services call
repositories; routes call services. This keeps persistence swappable
(Supabase/Postgres) and testable.
"""

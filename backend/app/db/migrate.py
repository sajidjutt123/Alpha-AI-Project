"""SQL migration runner.

Applies `database/migrations/*.sql` in filename order, exactly once, tracked
in the `schema_migrations` table. Optionally applies the dev seed.

Usage (from `backend/`):
    python -m app.db.migrate                # apply pending migrations
    python -m app.db.migrate --seed         # migrations + dev seed data

Requires an ADMIN connection string (owner/superuser — the runtime role
`alpha_app` cannot run DDL):
    ADMIN_DATABASE_URL=postgresql://alpha:alpha@localhost:5432/alpha_ai

Password substitution: `002_rls_roles.sql` contains the literal
`__APP_ROLE_PASSWORD__`, replaced with `APP_DB_PASSWORD` (default `alpha_app`,
dev only; validated to [A-Za-z0-9_-] to keep the SQL injectable-string-free).
"""

import asyncio
import os
import re
import sys
from pathlib import Path

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[3]
# Containers ship migrations at a different path — override with MIGRATIONS_DIR.
MIGRATIONS_DIR = Path(os.environ.get("MIGRATIONS_DIR") or REPO_ROOT / "database" / "migrations")
SEED_FILE = REPO_ROOT / "database" / "seed.sql"

PASSWORD_PLACEHOLDER = "__APP_ROLE_PASSWORD__"
_PASSWORD_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,128}$")


class MigrationError(RuntimeError):
    """Raised when migrations cannot be applied."""


def _safe_password(password: str) -> str:
    if not _PASSWORD_PATTERN.fullmatch(password):
        raise MigrationError(
            "APP_DB_PASSWORD must be 4-128 chars of [A-Za-z0-9_-] (it is interpolated into SQL DDL)"
        )
    return password


async def apply_migrations(
    admin_dsn: str,
    migrations_dir: Path = MIGRATIONS_DIR,
    app_role_password: str = "alpha_app",
) -> list[str]:
    """Apply pending migrations in order; return names of files applied."""
    password = _safe_password(app_role_password)

    if not migrations_dir.is_dir():
        raise MigrationError(f"migrations directory not found: {migrations_dir}")

    conn: asyncpg.Connection = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    text PRIMARY KEY,
                name       text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        applied = {
            record["version"]
            for record in await conn.fetch("SELECT version FROM schema_migrations")
        }

        files = sorted(migrations_dir.glob("*.sql"))
        if not files:
            raise MigrationError(f"no migration files found in {migrations_dir}")

        ran: list[str] = []
        for path in files:
            version = path.name.split("_", 1)[0]
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            if PASSWORD_PLACEHOLDER in sql:
                sql = sql.replace(PASSWORD_PLACEHOLDER, password)
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES ($1, $2)",
                    version,
                    path.stem,
                )
            ran.append(path.name)
        return ran
    finally:
        await conn.close()


async def apply_seed(admin_dsn: str, seed_file: Path = SEED_FILE) -> None:
    """Apply the (idempotent) development seed as an admin connection."""
    if not seed_file.is_file():
        raise MigrationError(f"seed file not found: {seed_file}")

    conn: asyncpg.Connection = await asyncpg.connect(admin_dsn)
    try:
        async with conn.transaction():
            await conn.execute(seed_file.read_text(encoding="utf-8"))
    finally:
        await conn.close()


def main() -> None:
    admin_dsn = os.environ.get("ADMIN_DATABASE_URL") or sys.exit(
        "ADMIN_DATABASE_URL is required (e.g. postgresql://alpha:alpha@localhost:5432/alpha_ai)"
    )
    password = os.environ.get("APP_DB_PASSWORD", "alpha_app")

    ran = asyncio.run(apply_migrations(admin_dsn, app_role_password=password))
    if ran:
        print(f"applied {len(ran)} migration(s):")
        for name in ran:
            print(f"  - {name}")
    else:
        print("database is up to date")

    if "--seed" in sys.argv:
        asyncio.run(apply_seed(admin_dsn))
        print("seed data applied")


if __name__ == "__main__":
    main()

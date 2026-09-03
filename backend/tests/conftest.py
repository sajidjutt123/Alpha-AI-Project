"""Pytest fixtures shared across backend tests.

Database provisioning:
- If TEST_DATABASE_URL (+ TEST_ADMIN_DATABASE_URL) are set (e.g. against
  `docker compose up -d db`), those are used.
- Otherwise an embedded PostgreSQL (pgserver, Postgres 16) is started under
  /tmp — no Docker required. Migrations are applied automatically.

The application connects as the RLS-bound `alpha_app` role; migrations run
on the admin connection. See app/core/database.py.
"""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import with_tenant
from app.db.migrate import apply_migrations
from app.main import create_app
from app.models import Organization
from app.repositories import OrganizationRepository

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_APP_PASSWORD = "alpha_app_test"


def _provision_database() -> tuple[str, str]:
    """Return (admin_dsn, app_dsn) for the test database, applying migrations."""
    external_url = os.environ.get("TEST_DATABASE_URL")
    if external_url:
        admin_url = os.environ.get("TEST_ADMIN_DATABASE_URL")
        if not admin_url:
            pytest.exit(
                "TEST_DATABASE_URL set without TEST_ADMIN_DATABASE_URL "
                "(migrations need an owner connection)",
                returncode=2,
            )
        asyncio.run(apply_migrations(admin_url, app_role_password=TEST_APP_PASSWORD))
        return admin_url, external_url

    import asyncpg
    import pgserver  # optional dev/test dependency

    server = pgserver.get_server("/tmp/alpha-ai-test-pg", cleanup_mode=None)
    bootstrap_dsn = server.get_uri("postgres")  # guaranteed to exist
    target_db = "alpha_ai_test"
    admin_dsn = server.get_uri(target_db)

    async def ensure_database() -> None:
        conn = await asyncpg.connect(bootstrap_dsn)
        try:
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", target_db)
            if not exists:
                await conn.execute(f'CREATE DATABASE "{target_db}"')
        finally:
            await conn.close()

    asyncio.run(ensure_database())
    asyncio.run(apply_migrations(admin_dsn, app_role_password=TEST_APP_PASSWORD))

    app_dsn = admin_dsn.replace(
        "postgresql://postgres:@/", f"postgresql://alpha_app:{TEST_APP_PASSWORD}@/"
    )
    # Keep a reference so the embedded server outlives fixture teardown.
    _PROVISIONED.append(server)
    return admin_dsn, app_dsn


_PROVISIONED: list[object] = []
_URLS: tuple[str, str] | None = None


def _database_urls() -> tuple[str, str]:
    global _URLS
    if _URLS is None:
        _URLS = _provision_database()
    return _URLS


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force deterministic settings for every test.

    `get_settings` is cached, so clear the cache after mutating the
    environment to guarantee a fresh `Settings` instance per test.
    """
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    _, app_dsn = _database_urls()
    monkeypatch.setenv("DATABASE_URL", app_dsn.replace("postgresql://", "postgresql+asyncpg://"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """HTTP client bound to a freshly built app instance."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Application-style session connected as the RLS-bound `alpha_app` role."""
    _, app_dsn = _database_urls()
    engine = create_async_engine(app_dsn.replace("postgresql://", "postgresql+asyncpg://"))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def organization(db_session: AsyncSession) -> AsyncIterator[Organization]:
    """A freshly created organization the test owns (tenant-isolated)."""
    org_id = uuid.uuid4()
    slug = f"test-org-{org_id.hex[:12]}"
    async with with_tenant(db_session, org_id):
        repo = OrganizationRepository(db_session)
        org = await repo.create(name="Test Estates", slug=slug, organization_id=org_id)
    yield org

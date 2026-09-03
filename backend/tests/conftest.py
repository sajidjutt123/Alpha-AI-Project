"""Pytest fixtures shared across backend tests.

Database provisioning:
- If TEST_DATABASE_URL (+ TEST_ADMIN_DATABASE_URL) are set (e.g. against
  `docker compose up -d db`), those are used.
- Otherwise an embedded PostgreSQL (pgserver, Postgres 16) is started under
  /tmp — no Docker required. Migrations are applied automatically.

Authentication in tests: tokens are minted with TEST_AUTH_SECRET via
`app.core.auth.issue_dev_token` (the app reads the same secret from
AUTH_DEV_SECRET). Each test organization gets agents with random
auth_user_id values — exercising the real JWT -> agent -> tenant path.
"""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import issue_dev_token
from app.core.config import get_settings
from app.core.database import with_tenant
from app.db.migrate import apply_migrations
from app.main import create_app
from app.models import Agent, Lead, Organization, Property
from app.models.enums import (
    LeadIntent,
    LeadStatus,
    MessageChannel,
    PropertyType,
    SenderType,
)
from app.repositories import (
    LeadRepository,
    MessageRepository,
    OrganizationRepository,
    PropertyRepository,
)
from app.repositories.agents import AgentRepository

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_APP_PASSWORD = "alpha_app_test"
TEST_AUTH_SECRET = "test-secret-not-for-production-0123456789"


def make_token(auth_user_id: str) -> str:
    return issue_dev_token(auth_user_id, TEST_AUTH_SECRET)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Database provisioning
# ---------------------------------------------------------------------------
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
    monkeypatch.setenv("AUTH_DEV_SECRET", TEST_AUTH_SECRET)
    _, app_dsn = _database_urls()
    monkeypatch.setenv("DATABASE_URL", app_dsn.replace("postgresql://", "postgresql+asyncpg://"))
    get_settings.cache_clear()
    # Engines must not outlive a test's event loop (see app.core.database).
    from app.core.database import get_engine, get_session_factory

    get_engine.cache_clear()
    get_session_factory.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


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


# ---------------------------------------------------------------------------
# Seeded organization context for API tests
# ---------------------------------------------------------------------------
@dataclass
class OrgContext:
    """A fully provisioned tenant plus a valid API token for its owner."""

    org: Organization
    owner: Agent
    teammate: Agent
    token: str
    leads: list[Lead] = field(default_factory=list)
    properties: list[Property] = field(default_factory=list)

    @property
    def headers(self) -> dict[str, str]:
        return auth_headers(self.token)


async def seed_organization(db_session: AsyncSession, *, name: str) -> OrgContext:
    """Create an org with owner+teammate agents, leads, properties, messages."""
    org_id = uuid.uuid4()
    owner_auth, teammate_auth = uuid.uuid4(), uuid.uuid4()
    digits = f"{uuid.uuid4().int % 10**8:08d}"
    whatsapp_from = f"whatsapp:+1415{digits[:8]}"
    sms_from = f"+1416{digits}"

    async with with_tenant(db_session, org_id):
        org = await OrganizationRepository(db_session).create(
            name=name,
            slug=f"{name.lower()}-{org_id.hex[:10]}",
            organization_id=org_id,
            twilio_whatsapp_from=whatsapp_from,
            twilio_sms_from=sms_from,
        )
        agents = AgentRepository(db_session)
        owner = await agents.add(
            Agent(
                organization_id=org_id,
                name="Owner One",
                email=f"owner-{org_id.hex[:8]}@example.com",
                role="OWNER",  # type: ignore[arg-type]
                auth_user_id=owner_auth,
            )
        )
        teammate = await agents.add(
            Agent(
                organization_id=org_id,
                name="Agent Two",
                email=f"agent-{org_id.hex[:8]}@example.com",
                role="AGENT",  # type: ignore[arg-type]
                auth_user_id=teammate_auth,
            )
        )

        props = PropertyRepository(db_session)
        properties = [
            await props.add(
                Property(
                    organization_id=org_id,
                    title="DHA Phase 6 House",
                    price=32_500_000,
                    location="DHA Phase 6, Lahore",
                    property_type=PropertyType.HOUSE,
                    bedrooms=4,
                )
            ),
            await props.add(
                Property(
                    organization_id=org_id,
                    title="Gulberg Apartment",
                    price=14_500_000,
                    location="Gulberg III, Lahore",
                    property_type=PropertyType.APARTMENT,
                    bedrooms=3,
                )
            ),
        ]

        leads_repo = LeadRepository(db_session)
        phone_digits = f"{uuid.uuid4().int % 10**8:08d}"  # digits only (E.164-safe)
        leads = [
            await leads_repo.add(
                Lead(
                    organization_id=org_id,
                    name="Ali Hassan",
                    phone=f"+923377{phone_digits[:5]}1",
                    status=LeadStatus.CONTACTED,
                    intent=LeadIntent.BUY,
                    qualification_score=60,
                    budget_min=25_000_000,
                    budget_max=35_000_000,
                    preferred_location="DHA Lahore",
                    assigned_agent_id=owner.id,
                )
            ),
            await leads_repo.add(
                Lead(
                    organization_id=org_id,
                    name="Sara Ahmed",
                    phone=f"+923377{phone_digits[:5]}2",
                    status=LeadStatus.QUALIFIED,
                    qualification_score=85,
                )
            ),
            await leads_repo.add(
                Lead(
                    organization_id=org_id,
                    name="Bilal Cheema",
                    phone=f"+923377{phone_digits[:5]}3",
                    status=LeadStatus.CONVERTED,
                    qualification_score=90,
                )
            ),
            await leads_repo.add(
                Lead(
                    organization_id=org_id,
                    name="Unnamed Caller",
                    phone=f"+923377{phone_digits[:5]}4",
                    status=LeadStatus.NEW,
                )
            ),
        ]

        messages = MessageRepository(db_session)
        await messages.add_message(
            lead_id=leads[0].id,
            sender_type=SenderType.CUSTOMER,
            content="I need a house in DHA.",
            channel=MessageChannel.WHATSAPP,
        )
        await messages.add_message(
            lead_id=leads[0].id,
            sender_type=SenderType.AI,
            content="Certainly — what budget range?",
            channel=MessageChannel.WHATSAPP,
        )

        from app.models import LeadPropertyMatch

        db_session.add(
            LeadPropertyMatch(
                lead_id=leads[0].id,
                property_id=properties[0].id,
                match_score=82,
                reason="Budget and location fit",
            )
        )
        await db_session.flush()

    return OrgContext(
        org=org,
        owner=owner,
        teammate=teammate,
        token=make_token(str(owner_auth)),
        leads=leads,
        properties=properties,
    )


@pytest.fixture
async def organization(db_session: AsyncSession) -> AsyncIterator[Organization]:
    """A freshly created organization the test owns (tenant-isolated)."""
    org_id = uuid.uuid4()
    slug = f"test-org-{org_id.hex[:12]}"
    async with with_tenant(db_session, org_id):
        repo = OrganizationRepository(db_session)
        org = await repo.create(name="Test Estates", slug=slug, organization_id=org_id)
    yield org


@pytest.fixture
async def org_context(db_session: AsyncSession) -> AsyncIterator[OrgContext]:
    context = await seed_organization(db_session, name="Alpha Test Estates")
    yield context


@pytest.fixture
async def other_org_context(db_session: AsyncSession) -> AsyncIterator[OrgContext]:
    context = await seed_organization(db_session, name="Beta Other Estates")
    yield context

"""Bootstrap CLI tests (Phase 10): first-run org provisioning."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import with_tenant
from app.db.bootstrap_org import bootstrap
from app.models import Agent, Organization


class TestBootstrapOrg:
    async def test_creates_org_and_owner(self, db_session: AsyncSession) -> None:
        auth_user_id = uuid.uuid4()
        # unique suffix: the shared test database persists across runs
        suffix = uuid.uuid4().hex[:8]
        organization = await bootstrap(
            db_session,
            name="Alpha Estates",
            slug=f"alpha-estates-{suffix}",
            owner_name="Ahmed Raza",
            owner_email=f"ahmed-{suffix}@example.com",
            auth_user_id=auth_user_id,
            twilio_whatsapp_from=f"whatsapp:+1415{uuid.uuid4().int % 10**8:08d}",
        )
        assert organization.id is not None
        assert organization.slug == f"alpha-estates-{suffix}"

        persisted = await db_session.get(Organization, organization.id)
        assert persisted is not None
        assert persisted.name == "Alpha Estates"

        # agents are RLS-scoped: verify inside the new tenant's context
        async with with_tenant(db_session, organization.id):
            agent = await db_session.scalar(
                select(Agent).where(Agent.email == f"ahmed-{suffix}@example.com")
            )
        assert agent is not None
        assert agent.organization_id == organization.id
        assert agent.role.value == "OWNER"
        assert agent.auth_user_id == auth_user_id

    async def test_duplicate_slug_refused(self, db_session: AsyncSession) -> None:
        suffix = uuid.uuid4().hex[:8]
        await bootstrap(
            db_session,
            name="First",
            slug=f"dup-slug-{suffix}",
            owner_name="A",
            owner_email=f"a-dup-{suffix}@example.com",
            auth_user_id=uuid.uuid4(),
            twilio_whatsapp_from=None,
        )
        with pytest.raises(SystemExit, match="uniqueness violated"):
            await bootstrap(
                db_session,
                name="Second",
                slug=f"dup-slug-{suffix}",
                owner_name="B",
                owner_email=f"b-dup-{suffix}@example.com",
                auth_user_id=uuid.uuid4(),
                twilio_whatsapp_from=None,
            )

    async def test_duplicate_auth_user_refused(self, db_session: AsyncSession) -> None:
        """auth_user_id is globally unique — one Supabase user maps to one
        agent across ALL organizations (RLS cannot see the other org's row,
        so the constraint is what catches it)."""
        suffix = uuid.uuid4().hex[:8]
        shared_auth_user = uuid.uuid4()
        await bootstrap(
            db_session,
            name="One",
            slug=f"org-one-{suffix}",
            owner_name="A",
            owner_email=f"a-{suffix}@example.com",
            auth_user_id=shared_auth_user,
            twilio_whatsapp_from=None,
        )
        with pytest.raises(SystemExit, match="uniqueness violated"):
            await bootstrap(
                db_session,
                name="Two",
                slug=f"org-two-{suffix}",
                owner_name="B",
                owner_email=f"b-{suffix}@example.com",
                auth_user_id=shared_auth_user,
                twilio_whatsapp_from=None,
            )

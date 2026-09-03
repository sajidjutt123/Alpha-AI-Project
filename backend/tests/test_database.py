"""Row Level Security — tenant isolation tests (Phase 2 gate).

These tests connect as the least-privilege `alpha_app` role and prove that:
- without tenant context nothing is visible,
- with tenant context only the own organization's rows are visible,
- cross-tenant writes are rejected by the database itself.
"""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from app.core.database import bind_tenant, with_tenant
from app.models import Lead, Message, Property
from app.models.enums import LeadStatus, MessageChannel, PropertyType, SenderType
from app.repositories import (
    LeadRepository,
    MessageRepository,
    OrganizationRepository,
    PropertyRepository,
)


async def _make_org(db_session, name: str):
    org_id = uuid.uuid4()
    async with with_tenant(db_session, org_id):
        org = await OrganizationRepository(db_session).create(
            name=name, slug=f"{name.lower()}-{org_id.hex[:8]}", organization_id=org_id
        )
    return org


async def _add_lead(db_session, org_id, phone: str) -> Lead:
    repo = LeadRepository(db_session)
    lead, _ = await repo.get_or_create_by_phone(organization_id=org_id, phone=phone)
    return lead


class TestTenantIsolation:
    async def test_no_tenant_context_sees_nothing(self, db_session) -> None:
        """Unbound connection: RLS quietly returns zero rows."""
        count = await db_session.scalar(select(func.count()).select_from(Lead))
        assert count == 0

    async def test_tenant_sees_only_own_leads(self, db_session, organization) -> None:
        other_org = await _make_org(db_session, "Other Estates")

        async with with_tenant(db_session, organization.id):
            await _add_lead(db_session, organization.id, "+923001110001")
        async with with_tenant(db_session, other_org.id):
            await _add_lead(db_session, other_org.id, "+923001110002")

            repo = LeadRepository(db_session)
            leads = await repo.list_for_organization(organization_id=other_org.id)
            assert len(leads) == 1
            assert leads[0].phone == "+923001110002"

    async def test_cross_tenant_insert_is_rejected(self, db_session, organization) -> None:
        """The database itself blocks writing into another organization."""
        other_org = await _make_org(db_session, "Victim Estates")

        with pytest.raises(DBAPIError):
            async with with_tenant(db_session, organization.id):
                await _add_lead(db_session, other_org.id, "+923001110003")

    async def test_messages_isolated_through_lead_join(self, db_session, organization) -> None:
        other_org = await _make_org(db_session, "Silent Estates")
        async with with_tenant(db_session, other_org.id):
            other_lead = await _add_lead(db_session, other_org.id, "+923002220001")
            await MessageRepository(db_session).add_message(
                lead_id=other_lead.id,
                sender_type=SenderType.CUSTOMER,
                content="secret message",
                channel=MessageChannel.WHATSAPP,
            )

        async with with_tenant(db_session, organization.id):
            visible = await db_session.scalars(select(Message))
            assert list(visible) == []

    async def test_tenant_context_resets_after_transaction(self, db_session, organization) -> None:
        """set_config(..., is_local => true) must not leak across transactions."""
        async with with_tenant(db_session, organization.id):
            pass  # binds and commits nothing

        count = await db_session.scalar(select(func.count()).select_from(Lead))
        assert count == 0


class TestSchemaContract:
    async def test_lead_defaults_and_check_constraints(self, db_session, organization) -> None:
        async with with_tenant(db_session, organization.id):
            lead, created = await LeadRepository(db_session).get_or_create_by_phone(
                organization_id=organization.id, phone="+923003330001"
            )

            assert created is True
            assert lead.status == LeadStatus.NEW
            assert lead.qualification_score is None

    async def test_phone_is_unique_per_organization(self, db_session, organization) -> None:
        repo = LeadRepository(db_session)
        async with with_tenant(db_session, organization.id):
            await repo.get_or_create_by_phone(
                organization_id=organization.id, phone="+923004440001"
            )

        async with with_tenant(db_session, organization.id):
            _, created = await repo.get_or_create_by_phone(
                organization_id=organization.id, phone="+923004440001"
            )
            assert created is False  # same org + phone -> existing lead

    async def test_updated_at_trigger_fires(self, db_session, organization) -> None:
        repo = LeadRepository(db_session)
        async with with_tenant(db_session, organization.id):
            lead = await _add_lead(db_session, organization.id, "+923005550001")
            first_updated = lead.updated_at

        async with with_tenant(db_session, organization.id):
            await repo.update_fields(lead, name="Updated Name")
            await db_session.refresh(lead)

        assert lead.updated_at >= first_updated


class TestCatalogSearch:
    async def test_property_search_filters(self, db_session, organization) -> None:
        repo = PropertyRepository(db_session)
        async with with_tenant(db_session, organization.id):
            for title, price, ptype, location, bedrooms in [
                ("House A", 32_500_000, PropertyType.HOUSE, "DHA Phase 6, Lahore", 3),
                ("House B", 68_000_000, PropertyType.HOUSE, "DHA Phase 5, Lahore", 5),
                ("Apartment C", 14_500_000, PropertyType.APARTMENT, "Gulberg III, Lahore", 3),
                ("Plot D", 9_800_000, PropertyType.PLOT, "DHA Phase 9 Prism, Lahore", None),
            ]:
                await repo.add(
                    Property(
                        organization_id=organization.id,
                        title=title,
                        price=price,
                        location=location,
                        property_type=ptype,
                        bedrooms=bedrooms,
                    )
                )

            houses = await repo.search(
                organization_id=organization.id, property_type=PropertyType.HOUSE
            )
            assert [p.title for p in houses] == ["House A", "House B"]

            in_budget = await repo.search(organization_id=organization.id, price_max=35_000_000)
            assert {p.title for p in in_budget} == {"House A", "Apartment C", "Plot D"}

            by_location = await repo.search(organization_id=organization.id, location="dha phase")
            assert {p.title for p in by_location} == {"House A", "House B", "Plot D"}

            by_bedrooms = await repo.search(organization_id=organization.id, bedrooms_min=4)
            assert [p.title for p in by_bedrooms] == ["House B"]

    async def test_search_never_crosses_tenants(self, db_session, organization) -> None:
        other_org = await _make_org(db_session, "Neighbour Estates")
        async with with_tenant(db_session, other_org.id):
            await PropertyRepository(db_session).add(
                Property(
                    organization_id=other_org.id,
                    title="Not Mine",
                    price=1_000_000,
                    location="Nowhere",
                    property_type=PropertyType.PLOT,
                )
            )

        async with with_tenant(db_session, organization.id):
            results = await PropertyRepository(db_session).search(organization_id=organization.id)
            assert results == []


class TestConversationTranscript:
    async def test_message_order_and_external_id_lookup(self, db_session, organization) -> None:
        external_id = f"SM-test-{uuid.uuid4().hex[:10]}"
        async with with_tenant(db_session, organization.id):
            lead = await _add_lead(db_session, organization.id, "+923006660001")
            repo = MessageRepository(db_session)
            await repo.add_message(
                lead_id=lead.id,
                sender_type=SenderType.CUSTOMER,
                content="first",
                channel=MessageChannel.WHATSAPP,
                external_message_id=external_id,
            )
            await repo.add_message(
                lead_id=lead.id,
                sender_type=SenderType.AI,
                content="second",
                channel=MessageChannel.WHATSAPP,
            )

            history = await repo.list_for_lead(lead.id)
            assert [m.content for m in history] == ["first", "second"]

            found = await repo.get_by_external_id(external_id)
            assert found is not None
            assert found.content == "first"


async def test_bind_tenant_uses_transaction_local_setting(db_session) -> None:
    """bind_tenant writes the documented GUC (guards the contract)."""
    org_id = uuid.uuid4()
    async with db_session.begin():
        await bind_tenant(db_session, org_id)
        current = await db_session.scalar(
            select(func.current_setting("app.current_organization_id", True))
        )
        assert current == str(org_id)

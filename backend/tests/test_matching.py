"""Deterministic matching service tests (plan Day 12)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import with_tenant
from app.models import Lead, LeadPropertyMatch
from app.models.enums import PropertyType
from app.services.matching import MatchingService
from tests.conftest import OrgContext


def make_lead(
    org_id: uuid.UUID,
    *,
    location: str | None = "DHA Lahore",
    ptype: PropertyType | None = PropertyType.HOUSE,
    budget_min: int | None = 20_000_000,
    budget_max: int | None = 30_000_000,
    bedrooms: int | None = 4,
) -> Lead:
    return Lead(
        organization_id=org_id,
        phone="+923000000000",
        preferred_location=location,
        property_type=ptype,
        budget_min=budget_min,
        budget_max=budget_max,
        bedrooms=bedrooms,
    )


class TestComponentScoring:
    def test_perfect_match_scores_full(self, org_context: OrgContext) -> None:
        from app.models import Property

        prop = Property(
            organization_id=org_context.org.id,
            title="Exact Home",
            price=25_000_000,
            location="DHA Phase 6, Lahore",
            property_type=PropertyType.HOUSE,
            bedrooms=4,
        )
        lead = make_lead(org_context.org.id)
        scored = MatchingService().score(lead, prop)

        assert scored.score == 100  # 40 + 25 (substring) + 15 + 20
        assert "within budget" in scored.reason.lower()
        assert "dha lahore" in scored.reason.lower()

    def test_budget_stretch_scores_partial(self, org_context: OrgContext) -> None:
        from app.models import Property

        prop = Property(
            organization_id=org_context.org.id,
            title="Stretch Home",
            price=33_000_000,  # 10% above the 30M ceiling
            location="DHA Phase 6, Lahore",
            property_type=PropertyType.HOUSE,
            bedrooms=4,
        )
        scored = MatchingService().score(make_lead(org_context.org.id), prop)
        assert scored.score == 85  # 25 stretch + 25 + 15 + 20

    def test_budget_far_out_scores_zero_budget(self, org_context: OrgContext) -> None:
        from app.models import Property

        prop = Property(
            organization_id=org_context.org.id,
            title="Mansion",
            price=90_000_000,
            location="DHA Phase 6, Lahore",
            property_type=PropertyType.HOUSE,
            bedrooms=4,
        )
        scored = MatchingService().score(make_lead(org_context.org.id), prop)
        # affordability gate caps an explicitly unaffordable property
        assert scored.score == 45
        assert "outside budget" in scored.reason

    def test_location_token_overlap_scores_partial(self, org_context: OrgContext) -> None:
        from app.models import Property

        prop = Property(
            organization_id=org_context.org.id,
            title="Other Side",
            price=25_000_000,
            location="Bahria Town, Lahore",  # shares "lahore" only
            property_type=PropertyType.HOUSE,
            bedrooms=4,
        )
        scored = MatchingService().score(make_lead(org_context.org.id), prop)
        assert scored.score == 87  # 40 + 12 (token) + 15 + 20

    def test_bedroom_off_by_one(self, org_context: OrgContext) -> None:
        from app.models import Property

        prop = Property(
            organization_id=org_context.org.id,
            title="Small DHA",
            price=25_000_000,
            location="DHA Phase 6, Lahore",
            property_type=PropertyType.HOUSE,
            bedrooms=5,
        )
        scored = MatchingService().score(make_lead(org_context.org.id), prop)
        assert scored.score == 92  # 40 + 25 + 15 + 12

    def test_unknown_preferences_score_neutral(self, org_context: OrgContext) -> None:

        lead = make_lead(
            org_context.org.id, location=None, ptype=None, budget_min=None, budget_max=None
        )
        assert MatchingService().ready(lead) is False  # nothing known — skip

    def test_type_mismatch_is_gated(self, org_context: OrgContext) -> None:
        from app.models import Property

        prop = Property(
            organization_id=org_context.org.id,
            title="Right price, wrong shape",
            price=25_000_000,
            location="DHA Phase 6, Lahore",
            property_type=PropertyType.PLOT,
            bedrooms=4,
        )
        scored = MatchingService().score(make_lead(org_context.org.id), prop)
        assert scored.score == 45  # gated below the recommendation threshold


class TestFindAndPersist:
    async def test_matches_persisted_and_replaced(
        self, db_session: AsyncSession, org_context: OrgContext
    ) -> None:
        lead = org_context.leads[3]  # blank slate lead
        service = MatchingService()

        async with with_tenant(db_session, org_context.org.id):
            lead.preferred_location = "Gulberg, Lahore"
            lead.property_type = PropertyType.APARTMENT
            lead.budget_min = 10_000_000
            lead.budget_max = 16_000_000
            lead.bedrooms = 3

            first = await service.find_and_persist(db_session, lead)
            assert [item.property.title for item in first] == ["Gulberg Apartment"]

            # requirements change → recommendations are REPLACED
            lead.preferred_location = "DHA Phase 6, Lahore"
            lead.property_type = PropertyType.HOUSE
            lead.budget_max = 40_000_000
            second = await service.find_and_persist(db_session, lead)
            assert [item.property.title for item in second] == ["DHA Phase 6 House"]

            rows = (
                (
                    await db_session.execute(
                        select(LeadPropertyMatch).where(LeadPropertyMatch.lead_id == lead.id)
                    )
                )
                .scalars()
                .all()
            )
            titles = {row.property_id for row in rows}
            assert titles == {second[0].property.id}  # stale match gone
            assert rows[0].match_score >= 50
            assert rows[0].reason

    async def test_no_match_returns_empty(
        self, db_session: AsyncSession, org_context: OrgContext
    ) -> None:
        lead = org_context.leads[3]
        async with with_tenant(db_session, org_context.org.id):
            lead.preferred_location = "Clifton, Karachi"
            lead.budget_min = 100_000_000
            lead.budget_max = 200_000_000
            matches = await MatchingService().find_and_persist(db_session, lead)
        assert matches == []

    async def test_matches_never_cross_tenants(
        self, db_session: AsyncSession, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        """A lead cannot match the other organization's catalogue."""
        lead = org_context.leads[3]
        async with with_tenant(db_session, org_context.org.id):
            lead.preferred_location = "Clifton Block 5, Karachi"  # only other org has this
            lead.property_type = PropertyType.APARTMENT
            lead.budget_min = 30_000_000
            lead.budget_max = 50_000_000
            lead.bedrooms = 4
            matches = await MatchingService().find_and_persist(db_session, lead)
        assert matches == []

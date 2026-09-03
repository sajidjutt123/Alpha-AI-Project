"""Deterministic scoring service tests (plan §7 math)."""

from app.models import Lead
from app.models.enums import LeadIntent, PropertyType
from app.services.scoring import ScoringService, ScoringWeights, Temperature


def make_lead(**overrides: object) -> Lead:
    defaults: dict[str, object] = {
        "organization_id": None,
        "phone": "+923000000000",
    }
    defaults.update(overrides)
    return Lead(**defaults)  # type: ignore[arg-type]


class TestComponentMath:
    def test_full_profile_scores_high(self) -> None:
        lead = make_lead(
            budget_min=20_000_000,
            budget_max=30_000_000,
            preferred_location="DHA Lahore",
            property_type=PropertyType.HOUSE,
            bedrooms=4,
            urgency_score=8,
        )
        breakdown = ScoringService().score(lead, customer_messages=6)

        assert breakdown.budget == 25
        assert breakdown.location == 20
        assert breakdown.urgency == 16
        assert breakdown.requirements == 20
        assert breakdown.engagement == 15
        assert breakdown.total == 96
        assert breakdown.temperature is Temperature.HOT

    def test_empty_profile_scores_zero(self) -> None:
        breakdown = ScoringService().score(make_lead(), customer_messages=0)

        assert breakdown.total == 0
        assert breakdown.temperature is Temperature.COLD

    def test_partial_budget_counts_partial(self) -> None:
        lead = make_lead(budget_max=30_000_000)
        assert ScoringService().score(lead, 0).budget == 15

    def test_engagement_saturates(self) -> None:
        lead = make_lead()
        service = ScoringService()
        assert service.score(lead, 1).engagement == 3.0
        assert service.score(lead, 5).engagement == 15.0
        assert service.score(lead, 50).engagement == 15.0

    def test_urgency_scales_to_max_20(self) -> None:
        lead = make_lead(urgency_score=10)
        assert ScoringService().score(lead, 0).urgency == 20


class TestThresholds:
    def test_default_thresholds_match_plan(self) -> None:
        service = ScoringService()
        assert service.classify(80) is Temperature.HOT
        assert service.classify(79) is Temperature.WARM
        assert service.classify(50) is Temperature.WARM
        assert service.classify(49) is Temperature.COLD

    def test_thresholds_are_configurable(self) -> None:
        service = ScoringService(hot_threshold=70, warm_threshold=40)
        assert service.classify(70) is Temperature.HOT
        assert service.classify(45) is Temperature.WARM
        assert service.classify(39) is Temperature.COLD

    def test_weights_are_configurable(self) -> None:
        weights = ScoringWeights(
            budget_complete=50,
            budget_partial=30,
            location=0,
            urgency_multiplier=0,
            requirement_property_type=0,
            requirement_bedrooms=0,
            engagement_max=0,
        )
        lead = make_lead(budget_min=1, budget_max=2)
        assert ScoringService(weights=weights).score(lead, 9).total == 50


class TestBounds:
    def test_total_clamped_to_100(self) -> None:
        weights = ScoringWeights(
            budget_complete=100,
            budget_partial=100,
            location=100,
            urgency_multiplier=100,
            requirement_property_type=100,
            requirement_bedrooms=100,
            engagement_max=100,
        )
        lead = make_lead(
            budget_min=1,
            budget_max=2,
            preferred_location="x",
            property_type=PropertyType.PLOT,
            bedrooms=5,
            urgency_score=10,
        )
        assert ScoringService(weights=weights).score(lead, 10).total == 100

    def test_intent_is_not_scored(self) -> None:
        """Scoring ignores intent — facts only (LLM doesn't inflate scores)."""
        buyer = make_lead(intent=LeadIntent.BUY)
        browser = make_lead(intent=LeadIntent.GENERAL_INQUIRY)
        service = ScoringService()
        assert service.score(buyer, 0).total == service.score(browser, 0).total

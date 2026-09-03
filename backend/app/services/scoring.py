"""Deterministic lead qualification scoring (plan §7).

The LLM never decides a lead's score — it only reports the customer's
stated requirements. This service turns those facts into a 0..100 score
with configurable component weights (defaults follow the plan):

    budget        25   both bounds known 25, one 15, none 0
    location      20   preferred_location known
    urgency       20   urgency_score (1..10) * 2
    requirements  20   property_type (10) + bedrooms (10)
    engagement    15   customer messages, saturating at 5

Classification: >= hot_threshold (80) HOT, >= warm_threshold (50) WARM,
else COLD. Thresholds and weights are configuration, not prompt text.
"""

import enum
from dataclasses import dataclass

from app.models import Lead


class Temperature(enum.StrEnum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


@dataclass(frozen=True)
class ScoringWeights:
    budget_complete: float = 25.0
    budget_partial: float = 15.0
    location: float = 20.0
    urgency_multiplier: float = 2.0  # urgency_score * multiplier (10 -> 20)
    requirement_property_type: float = 10.0
    requirement_bedrooms: float = 10.0
    engagement_max: float = 15.0
    engagement_saturating_messages: int = 5


@dataclass(frozen=True)
class ScoreBreakdown:
    budget: float
    location: float
    urgency: float
    requirements: float
    engagement: float
    total: int
    temperature: Temperature


class ScoringService:
    """Score a lead from captured facts. Deterministic and configurable."""

    def __init__(
        self,
        *,
        weights: ScoringWeights | None = None,
        hot_threshold: int = 80,
        warm_threshold: int = 50,
    ) -> None:
        self.weights = weights or ScoringWeights()
        self.hot_threshold = hot_threshold
        self.warm_threshold = warm_threshold

    def score(self, lead: Lead, customer_messages: int) -> ScoreBreakdown:
        w = self.weights

        if lead.budget_min is not None and lead.budget_max is not None:
            budget = w.budget_complete
        elif lead.budget_min is not None or lead.budget_max is not None:
            budget = w.budget_partial
        else:
            budget = 0.0

        location = w.location if lead.preferred_location else 0.0
        urgency = (lead.urgency_score or 0) * w.urgency_multiplier
        requirements = (w.requirement_property_type if lead.property_type else 0.0) + (
            w.requirement_bedrooms if lead.bedrooms else 0.0
        )
        engagement = (
            w.engagement_max
            * min(customer_messages, w.engagement_saturating_messages)
            / w.engagement_saturating_messages
        )

        total = round(budget + location + urgency + requirements + engagement)
        return ScoreBreakdown(
            budget=budget,
            location=location,
            urgency=urgency,
            requirements=requirements,
            engagement=engagement,
            total=max(0, min(100, total)),
            temperature=self.classify(total),
        )

    def classify(self, total: int) -> Temperature:
        if total >= self.hot_threshold:
            return Temperature.HOT
        if total >= self.warm_threshold:
            return Temperature.WARM
        return Temperature.COLD

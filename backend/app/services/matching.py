"""Deterministic property matching (plan Day 12).

The AI never picks properties — it extracts requirements; this service
scores every candidate against the lead with explainable component weights:

    budget     40   inside [min,max] 40; within 15% of the range 25; else 0
    location   25   all preferred tokens present 25; any token 12; else 0
    type       15   matches 15; preference unknown 8; mismatch 0
    bedrooms   20   exact 20; one off 12; >=2 off 0; unknown 10

Deterministic gates (business rules, not weights): an explicitly
unaffordable property (budget score 0 with a stated budget) or an explicit
type mismatch is capped at 45 — never recommended, whatever else matches.

Matches at or above `match_score_threshold` (default 50) are persisted to
`lead_property_matches` (replacing prior recommendations) with a
human-readable reason. Pure functions + persistence — no LLM involved.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Lead, LeadPropertyMatch, Property
from app.repositories import PropertyRepository

logger = logging.getLogger(__name__)

_CANDIDATE_POOL = 100  # broad candidate fetch; scored precisely in Python
_GATE_CAP = 45  # one below the default threshold: gated, never recommended


@dataclass(frozen=True)
class ScoredProperty:
    property: Property
    score: int
    reason: str


def _budget_score(lead: Lead, price: int) -> tuple[float, str]:
    floor, ceiling = lead.budget_min, lead.budget_max
    if floor is not None and ceiling is not None:
        if floor <= price <= ceiling:
            return 40.0, "within budget"
        if floor * 0.85 <= price <= ceiling * 1.15:
            return 25.0, "close to budget range"
        return 0.0, "outside budget"
    if ceiling is not None:
        if price <= ceiling:
            return 40.0, "within budget"
        if price <= ceiling * 1.15:
            over = round((price / ceiling - 1) * 100)
            return 25.0, f"{over}% above budget ceiling"
        return 0.0, "outside budget"
    if floor is not None:
        if price >= floor:
            return 40.0, "within budget (floor only)"
        if price >= floor * 0.85:
            return 25.0, "close to budget floor"
        return 0.0, "below budget floor"
    return 0.0, ""


def _location_tokens(preferred: str) -> list[str]:
    return [t for t in preferred.strip().lower().replace(",", " ").split() if len(t) >= 3]


def _location_score(preferred: str | None, location: str) -> tuple[float, str]:
    if not preferred:
        return 0.0, ""
    target = location.lower()
    tokens = _location_tokens(preferred)
    if tokens and all(token in target for token in tokens):
        return 25.0, f"matches {preferred.strip()}"
    if tokens and any(token in target for token in tokens):
        return 12.0, f"near {preferred.strip()}"
    return 0.0, ""


def _type_score(lead: Lead, prop: Property) -> tuple[float, str]:
    if lead.property_type is None:
        return 8.0, ""
    if lead.property_type == prop.property_type:
        return 15.0, "type matches"
    return 0.0, f"different type ({prop.property_type.value.lower()})"


def _bedrooms_score(lead: Lead, prop: Property) -> tuple[float, str]:
    if lead.bedrooms is None or prop.bedrooms is None:
        return 10.0, ""
    if lead.bedrooms == prop.bedrooms:
        return 20.0, "bedrooms match"
    if abs(lead.bedrooms - prop.bedrooms) == 1:
        return 12.0, "one bedroom off"
    return 0.0, f"{prop.bedrooms} bed vs {lead.bedrooms} wanted"


class MatchingService:
    """Score a lead against the organization's catalogue deterministically."""

    def score(self, lead: Lead, prop: Property) -> ScoredProperty:
        parts: list[str] = []
        total = 0.0

        budget, budget_reason = _budget_score(lead, prop.price)
        total += budget
        if budget_reason:
            parts.append(budget_reason)

        location, location_reason = _location_score(lead.preferred_location, prop.location)
        total += location
        if location_reason:
            parts.append(location_reason)

        type_score, type_reason = _type_score(lead, prop)
        total += type_score
        if type_reason:
            parts.append(type_reason)

        bedrooms, bedrooms_reason = _bedrooms_score(lead, prop)
        total += bedrooms
        if bedrooms_reason:
            parts.append(bedrooms_reason)

        score = max(0, min(100, round(total)))
        budget_known = lead.budget_min is not None or lead.budget_max is not None
        unaffordable = budget_known and budget == 0.0
        type_mismatch = lead.property_type is not None and lead.property_type != prop.property_type
        if unaffordable or type_mismatch:
            score = min(score, _GATE_CAP)  # never recommended despite other fits
            if unaffordable:
                parts.append("not recommended: outside budget")
            else:
                parts.append("not recommended: different type")

        return ScoredProperty(
            property=prop,
            score=score,
            reason="; ".join(parts).capitalize() if parts else "No explicit preferences",
        )

    @staticmethod
    def ready(lead: Lead) -> bool:
        """Matching runs only once the lead expressed at least one preference."""
        return any(
            [
                lead.preferred_location,
                lead.property_type is not None,
                lead.budget_min is not None,
                lead.budget_max is not None,
            ]
        )

    async def find_matches(self, session: AsyncSession, lead: Lead) -> list[ScoredProperty]:
        """Score the catalogue and return matches above the threshold, best first."""
        if not self.ready(lead):
            return []
        settings = get_settings()
        candidates: Sequence[Property] = await PropertyRepository(session).search(
            organization_id=lead.organization_id,
            price_max=_search_ceiling(lead),
            limit=_CANDIDATE_POOL,
        )
        scored = sorted(
            (self.score(lead, prop) for prop in candidates),
            key=lambda item: item.score,
            reverse=True,
        )
        return [item for item in scored if item.score >= settings.match_score_threshold][
            : settings.match_recommendation_limit
        ]

    async def find_and_persist(self, session: AsyncSession, lead: Lead) -> list[ScoredProperty]:
        """Refresh the lead's stored recommendations (replace semantics)."""
        matches = await self.find_matches(session, lead)
        await session.execute(delete(LeadPropertyMatch).where(LeadPropertyMatch.lead_id == lead.id))
        for item in matches:
            session.add(
                LeadPropertyMatch(
                    lead_id=lead.id,
                    property_id=item.property.id,
                    match_score=item.score,
                    reason=item.reason,
                )
            )
        await session.flush()
        if matches:
            logger.info(
                "property_matches_persisted",
                extra={
                    "lead_id": str(lead.id),
                    "count": len(matches),
                    "top": matches[0].score,
                },
            )
        return matches


def _search_ceiling(lead: Lead) -> int | None:
    """Query ceiling: allow 20% stretch above the stated maximum."""
    if lead.budget_max is not None:
        return int(lead.budget_max * 1.20)
    return None


__all__ = ["MatchingService", "ScoredProperty"]

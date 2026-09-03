"""Analytics API contracts."""

from pydantic import BaseModel

from app.models.enums import LeadStatus


class AnalyticsOverview(BaseModel):
    total_leads: int
    by_status: dict[LeadStatus, int]
    hot_leads: int  # qualification_score >= 80
    warm_leads: int  # 50..79
    cold_leads: int  # < 50 or unscored
    conversion_rate: float  # CONVERTED / total (0..1)
    avg_qualification_score: float | None
    new_leads_7d: int
    total_properties: int

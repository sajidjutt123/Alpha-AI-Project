"""Analytics service — command-center overview metrics."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadStatus
from app.repositories import AnalyticsRepository
from app.schemas.analytics import AnalyticsOverview

HOT_THRESHOLD = 80
WARM_THRESHOLD = 50


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AnalyticsRepository(session)

    async def overview(self, organization_id: uuid.UUID) -> AnalyticsOverview:
        by_status = await self.repo.counts_by_status()
        total = sum(by_status.values())
        hot, warm, cold = await self.repo.temperature_counts()
        converted = by_status.get(LeadStatus.CONVERTED, 0)

        return AnalyticsOverview(
            total_leads=total,
            by_status={status: by_status.get(status, 0) for status in LeadStatus},
            hot_leads=hot,
            warm_leads=warm,
            cold_leads=cold,
            conversion_rate=(converted / total) if total else 0.0,
            avg_qualification_score=await self.repo.avg_qualification_score(),
            new_leads_7d=await self.repo.new_leads_since(7),
            total_properties=await self.repo.total_properties(organization_id),
        )

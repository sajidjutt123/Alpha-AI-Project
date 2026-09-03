"""Analytics queries (all tenant-scoped through RLS-bound session)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, Property
from app.models.enums import LeadStatus


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def counts_by_status(self) -> dict[LeadStatus, int]:
        result = await self.session.execute(select(Lead.status, func.count()).group_by(Lead.status))
        return {status: int(count) for status, count in result.all()}

    async def temperature_counts(self) -> tuple[int, int, int]:
        """(hot, warm, cold) by qualification score; unscored counts as cold."""
        hot = func.count(case((Lead.qualification_score >= 80, 1)))
        warm = func.count(
            case(
                (
                    and_(
                        Lead.qualification_score >= 50,
                        Lead.qualification_score < 80,
                    ),
                    1,
                )
            )
        )
        result = await self.session.execute(select(func.count(), hot, warm).select_from(Lead))
        total, hot_n, warm_n = result.one()
        return int(hot_n), int(warm_n), int(total) - int(hot_n) - int(warm_n)

    async def avg_qualification_score(self) -> float | None:
        result = await self.session.execute(select(func.avg(Lead.qualification_score)))
        value = result.scalar_one()
        return float(value) if value is not None else None

    async def new_leads_since(self, days: int) -> int:
        since = datetime.now(tz=UTC) - timedelta(days=days)
        result = await self.session.execute(
            select(func.count()).select_from(Lead).where(Lead.created_at >= since)
        )
        return int(result.scalar_one())

    async def total_properties(self, organization_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Property)
            .where(Property.organization_id == organization_id)
        )
        return int(result.scalar_one())

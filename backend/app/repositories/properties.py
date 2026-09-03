"""Property repository + catalog search."""

import uuid
from collections.abc import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Property, PropertyType
from app.repositories.base import BaseRepository


class PropertyRepository(BaseRepository[Property]):
    model = Property

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def search(
        self,
        *,
        organization_id: uuid.UUID,
        property_type: PropertyType | None = None,
        location: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        bedrooms_min: int | None = None,
        limit: int = 20,
    ) -> Sequence[Property]:
        """Search an organization's catalogue.

        Backing implementation for the AI `search_properties` tool and the
        dashboard property browser. Location matches case-insensitively as
        a substring ("DHA" matches "DHA Phase 6, Lahore").
        """
        conditions = [Property.organization_id == organization_id]
        if property_type is not None:
            conditions.append(Property.property_type == property_type)
        if location:
            conditions.append(Property.location.ilike(f"%{location}%"))
        if price_min is not None:
            conditions.append(Property.price >= price_min)
        if price_max is not None:
            conditions.append(Property.price <= price_max)
        if bedrooms_min is not None:
            conditions.append(
                and_(
                    Property.bedrooms.is_not(None),
                    Property.bedrooms >= bedrooms_min,
                )
            )

        stmt = select(Property).where(and_(*conditions)).order_by(Property.price.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_organization(self, organization_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Property)
            .where(Property.organization_id == organization_id)
        )
        return int(result.scalar_one())

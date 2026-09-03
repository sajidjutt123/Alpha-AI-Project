"""Property service — catalogue management."""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Property
from app.models.enums import PropertyType
from app.repositories import PropertyRepository
from app.schemas.properties import PropertyCreate


class PropertyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.properties = PropertyRepository(session)

    async def create_property(
        self, organization_id: uuid.UUID, payload: PropertyCreate
    ) -> Property:
        prop = Property(
            organization_id=organization_id,
            **payload.model_dump(),
        )
        return await self.properties.add(prop)

    async def get_property(self, organization_id: uuid.UUID, property_id: uuid.UUID) -> Property:
        prop = await self.properties.get(property_id)
        if prop is None or prop.organization_id != organization_id:
            raise NotFoundError(f"Property {property_id} not found")
        return prop

    async def search_properties(
        self,
        organization_id: uuid.UUID,
        *,
        property_type: PropertyType | None = None,
        location: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        bedrooms_min: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Property], int]:
        items = await self.properties.search(
            organization_id=organization_id,
            property_type=property_type,
            location=location,
            price_min=price_min,
            price_max=price_max,
            bedrooms_min=bedrooms_min,
            limit=limit,
        )
        total = await self.properties.count_search(
            organization_id,
            property_type=property_type,
            location=location,
            price_min=price_min,
            price_max=price_max,
            bedrooms_min=bedrooms_min,
        )
        return items, total

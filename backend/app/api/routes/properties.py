"""Property endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AgentDep, TenantDb
from app.models.enums import PropertyType
from app.schemas.pagination import Page
from app.schemas.properties import PropertyCreate, PropertyOut
from app.services import PropertyService

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=Page[PropertyOut])
async def list_properties(
    db: TenantDb,
    agent: AgentDep,
    property_type: Annotated[PropertyType | None, Query()] = None,
    location: Annotated[str | None, Query(max_length=100)] = None,
    price_min: Annotated[int | None, Query(ge=0)] = None,
    price_max: Annotated[int | None, Query(ge=0)] = None,
    bedrooms_min: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[PropertyOut]:
    items, total = await PropertyService(db).search_properties(
        agent.organization_id,
        property_type=property_type,
        location=location,
        price_min=price_min,
        price_max=price_max,
        bedrooms_min=bedrooms_min,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[PropertyOut.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
async def create_property(payload: PropertyCreate, db: TenantDb, agent: AgentDep) -> PropertyOut:
    prop = await PropertyService(db).create_property(agent.organization_id, payload)
    return PropertyOut.model_validate(prop)


@router.get("/{property_id}", response_model=PropertyOut)
async def get_property(property_id: uuid.UUID, db: TenantDb, agent: AgentDep) -> PropertyOut:
    prop = await PropertyService(db).get_property(agent.organization_id, property_id)
    return PropertyOut.model_validate(prop)

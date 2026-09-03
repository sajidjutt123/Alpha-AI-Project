"""Validated AI tools (plan §8).

The graph (and, later, LLM tool-calling) goes through `ToolExecutor` — the
single choke point where every tool request is validated against a Pydantic
param schema and executed against the tenant-bound session:

    request -> validate params -> audit log -> execute -> result

The LLM can never touch the database directly, and tool parameters (limits,
ids, filters) are clamped/validated before any query runs. Invocation is
deterministic in V1 (graph nodes call tools); the same executor will
validate model-initiated tool calls if that mode is enabled later.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Property
from app.models.enums import PropertyType
from app.repositories import PropertyRepository

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Unknown tool or invalid parameters — never retried blindly."""


class SearchPropertiesParams(BaseModel):
    location: str | None = Field(default=None, max_length=100)
    property_type: PropertyType | None = None
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    bedrooms_min: int | None = Field(default=None, ge=0, le=20)
    limit: int = Field(default=10, ge=1, le=20)  # hard cap: one page max


class GetPropertyDetailsParams(BaseModel):
    property_id: UUID


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    params: type[BaseModel]
    handler: Callable[..., Awaitable[Any]]


async def _search_properties(
    session: AsyncSession, organization_id: UUID, params: SearchPropertiesParams
) -> dict[str, Any]:
    rows = await PropertyRepository(session).search(
        organization_id=organization_id,
        property_type=params.property_type,
        location=params.location,
        price_min=params.price_min,
        price_max=params.price_max,
        bedrooms_min=params.bedrooms_min,
        limit=params.limit,
    )
    return {
        "count": len(rows),
        "properties": [_property_summary(prop) for prop in rows],
    }


async def _get_property_details(
    session: AsyncSession, organization_id: UUID, params: GetPropertyDetailsParams
) -> dict[str, Any]:
    prop = await PropertyRepository(session).get(params.property_id)
    if prop is None or prop.organization_id != organization_id:
        raise NotFoundError(f"Property {params.property_id} not found")
    return _property_summary(prop)


def _property_summary(prop: Property) -> dict[str, Any]:
    return {
        "id": str(prop.id),
        "title": prop.title,
        "price": prop.price,
        "location": prop.location,
        "property_type": prop.property_type.value,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "area_sqft": prop.area,
        "availability": prop.availability.value,
    }


TOOLS: dict[str, Tool] = {
    "search_properties": Tool(
        name="search_properties",
        description="Search the organization's property catalogue with filters.",
        params=SearchPropertiesParams,
        handler=_search_properties,
    ),
    "get_property_details": Tool(
        name="get_property_details",
        description="Fetch one property by id (organization-scoped).",
        params=GetPropertyDetailsParams,
        handler=_get_property_details,
    ),
}


class ToolExecutor:
    """Validate + execute tool requests against a tenant-bound session."""

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    async def execute(self, name: str, params: dict[str, Any] | None = None) -> Any:
        tool = TOOLS.get(name)
        if tool is None:
            raise ToolError(f"Unknown tool: {name}")
        try:
            validated = tool.params.model_validate(params or {})
        except ValidationError as exc:
            raise ToolError(f"Invalid parameters for {name}: {exc.error_count()} errors") from exc

        logger.info(
            "tool_executed",
            extra={"tool": name, "organization_id": str(self.organization_id)},
        )
        return await tool.handler(self.session, self.organization_id, validated)


__all__ = ["TOOLS", "Tool", "ToolError", "ToolExecutor"]

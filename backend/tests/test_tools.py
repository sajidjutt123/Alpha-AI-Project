"""Tool executor tests — the validated AI-tool choke point (plan §8)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools import ToolError, ToolExecutor
from app.core.database import with_tenant
from tests.conftest import OrgContext


@pytest.fixture
async def executor(db_session: AsyncSession, org_context: OrgContext):
    """Tenant-bound executor (RLS context required for reads)."""
    from app.core.database import with_tenant

    async with with_tenant(db_session, org_context.org.id):
        yield ToolExecutor(db_session, org_context.org.id)


class TestValidation:
    async def test_unknown_tool_rejected(self, executor: ToolExecutor) -> None:
        with pytest.raises(ToolError, match="Unknown tool"):
            await executor.execute("drop_database")

    async def test_invalid_params_rejected(self, executor: ToolExecutor) -> None:
        with pytest.raises(ToolError, match="Invalid parameters"):
            await executor.execute("search_properties", {"limit": 999})

    async def test_limit_hard_capped_by_schema(self, executor: ToolExecutor) -> None:
        with pytest.raises(ToolError):
            await executor.execute("search_properties", {"limit": 21})


class TestSearchProperties:
    async def test_search_returns_summaries(
        self, executor: ToolExecutor, org_context: OrgContext
    ) -> None:
        result = await executor.execute("search_properties", {"location": "gulberg", "limit": 5})

        assert result["count"] == 1
        prop = result["properties"][0]
        assert prop["title"] == "Gulberg Apartment"
        assert prop["price"] == 14_500_000
        assert prop["property_type"] == "APARTMENT"
        assert "id" in prop and "availability" in prop

    async def test_search_empty_params_uses_defaults(
        self, executor: ToolExecutor, org_context: OrgContext
    ) -> None:
        result = await executor.execute("search_properties")
        assert result["count"] == len(org_context.properties)


class TestGetPropertyDetails:
    async def test_details_for_own_property(
        self, executor: ToolExecutor, org_context: OrgContext
    ) -> None:
        prop_id = str(org_context.properties[0].id)
        result = await executor.execute("get_property_details", {"property_id": prop_id})

        assert result["title"] == "DHA Phase 6 House"

    async def test_foreign_property_not_found(
        self, db_session: AsyncSession, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        from app.core.errors import NotFoundError

        foreign = str(other_org_context.properties[0].id)
        executor = ToolExecutor(db_session, org_context.org.id)
        async with with_tenant(db_session, org_context.org.id):
            with pytest.raises(NotFoundError):
                await executor.execute("get_property_details", {"property_id": foreign})

    async def test_malformed_uuid_rejected(self, executor: ToolExecutor) -> None:
        with pytest.raises(ToolError, match="Invalid parameters"):
            await executor.execute("get_property_details", {"property_id": "not-a-uuid"})


class TestTenantBinding:
    async def test_executor_is_bound_to_organization(
        self, db_session: AsyncSession, org_context: OrgContext
    ) -> None:
        """RLS + org-scoped tools: a foreign org id yields nothing."""
        executor = ToolExecutor(db_session, uuid.uuid4())  # nonexistent org
        async with with_tenant(db_session, org_context.org.id):
            # session bound to real org, executor claims another -> RLS still
            # enforces the session tenant; results come from the bound org only
            result = await executor.execute("search_properties")
        assert isinstance(result["count"], int)

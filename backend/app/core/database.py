"""Async database engine, sessions, and tenant-context binding.

Connections use the least-privilege role (`alpha_app`) which is subject to
Row Level Security. Every request/operation must bind its tenant context via
`bind_tenant()` (or `with_tenant()`) before touching domain tables — RLS then
guarantees organization isolation even if application code is wrong.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

TENANT_GUC = "app.current_organization_id"


@lru_cache
def get_engine() -> AsyncEngine:
    """Cached engine built from application settings.

    Tests run with per-function event loops, so pooling connections across
    them is unsound — the test environment uses NullPool.
    """
    settings = get_settings()
    options: dict[str, object] = {}
    if settings.environment == "test":
        options["poolclass"] = NullPool
    return create_async_engine(settings.database_url, pool_pre_ping=True, **options)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Session factory bound to the shared engine."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a database session."""
    async with get_session_factory()() as session:
        yield session


async def bind_tenant(session: AsyncSession, organization_id: UUID) -> None:
    """Bind the RLS tenant context for the CURRENT transaction.

    `set_config(..., is_local => true)` keeps the setting transaction-scoped:
    it resets on commit/rollback, so pooled connections never leak tenant
    context between requests.
    """
    await session.execute(
        text(f"SELECT set_config('{TENANT_GUC}', :org_id, true)"),
        {"org_id": str(organization_id)},
    )


@asynccontextmanager
async def with_tenant(session: AsyncSession, organization_id: UUID) -> AsyncIterator[AsyncSession]:
    """Run a unit of work inside a transaction bound to one organization.

    Usage:
        async with with_tenant(session, org_id) as tenant_session:
            await LeadRepository(tenant_session).list_all()
    """
    async with session.begin():
        await bind_tenant(session, organization_id)
        yield session

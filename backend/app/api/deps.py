"""Shared request-scoped dependencies: database session, auth, tenant binding.

Request lifecycle:
    1. `get_auth_principal` verifies the bearer JWT (signature + expiry).
    2. `get_agent_context` resolves the auth user to an active agent via the
       SECURITY DEFINER function `app_agent_by_auth_user` (auth bootstrap —
       must work before any tenant context exists).
    3. `get_tenant_db` opens the request transaction and binds the RLS
       tenant context; it commits on success and rolls back on error.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_token
from app.core.database import bind_tenant, get_db
from app.models.enums import AgentRole

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AgentContext:
    """The authenticated caller, resolved to an agent row."""

    agent_id: UUID
    organization_id: UUID
    role: AgentRole
    name: str
    email: str


async def get_auth_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        principal = decode_token(credentials.credentials)
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return principal.auth_user_id


async def get_agent_context(
    auth_user_id: Annotated[str, Depends(get_auth_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentContext:
    result = await db.execute(
        text(
            "SELECT agent_id, organization_id, role, name, email FROM app_agent_by_auth_user(:uid)"
        ),
        {"uid": auth_user_id},
    )
    row = result.mappings().first()
    # Close the implicit transaction the lookup opened so the request's
    # tenant transaction can begin cleanly (see get_tenant_db).
    await db.rollback()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user is not an active agent of any organization",
        )
    return AgentContext(
        agent_id=row["agent_id"],
        organization_id=row["organization_id"],
        role=AgentRole(row["role"]),
        name=row["name"],
        email=row["email"],
    )


async def get_tenant_db(
    agent: Annotated[AgentContext, Depends(get_agent_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncIterator[AsyncSession]:
    """Yield a session inside a tenant-bound transaction.

    Handlers use it directly (reads see only the caller's organization; the
    transaction commits when the request completes without error).
    """
    async with db.begin():
        await bind_tenant(db, agent.organization_id)
        yield db


AgentDep = Annotated[AgentContext, Depends(get_agent_context)]
TenantDb = Annotated[AsyncSession, Depends(get_tenant_db)]

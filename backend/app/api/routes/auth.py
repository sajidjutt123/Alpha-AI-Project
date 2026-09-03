"""Authentication endpoints.

`POST /auth/dev-login` exists for local development and demos: it trades a
seeded agent email for a JWT minted with AUTH_DEV_SECRET — the exact same
token format and downstream verification path (JWT → agent → tenant) used
with Supabase Auth in production. The endpoint hard-refuses outside
development/test environments; production dashboards authenticate through
Supabase Auth and send their access_token as the bearer.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import issue_dev_token
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.schemas.auth import DevLoginRequest, SessionAgent, TokenResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/dev-login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("dev-login"))],
)
async def dev_login(
    payload: DevLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    settings = get_settings()
    if settings.environment in ("production", "staging") or not settings.auth_dev_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")

    result = await db.execute(
        text(
            "SELECT agent_id, organization_id, role, name, email, auth_user_id "
            "FROM app_agent_by_email(:email)"
        ),
        {"email": payload.email.lower()},
    )
    row = result.mappings().first()
    await db.rollback()
    if row is None:
        logger.warning("dev_login_unknown_email", extra={"email": payload.email})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown agent email")

    token = issue_dev_token(str(row["auth_user_id"]), settings.auth_dev_secret)
    agent = SessionAgent(
        id=row["agent_id"],
        name=row["name"],
        email=row["email"],
        role=row["role"],
        organization_id=row["organization_id"],
    )
    logger.info("dev_login", extra={"agent": agent.email})
    return TokenResponse(token=token, agent=agent)

"""Realtime SSE stream.

`GET /api/v1/realtime/stream` — one long-lived connection per dashboard
tab, carrying every event for the caller's organization:

    event: message.created      data: {lead_id, message_id, sender_type, preview}
    event: lead.created         data: {lead_id, name, phone}
    event: lead.updated         data: {lead_id, status, qualification_score}
    event: handoff.requested    data: {lead_id}
    event: notification.created data: {id, type, title, lead_id}

Auth is the standard bearer token. The agent is resolved up front and the
session's transaction is released BEFORE streaming begins — the SSE
connection lives for minutes and must not hold a pooled DB connection.
Keepalive comments keep proxies from idling out. Multi-instance scale path:
swap the in-process bus for Redis pub/sub (see docs/architecture.md).
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer_scheme, get_agent_context, get_auth_principal
from app.core.database import get_db
from app.core.events import KEEPALIVE_SECONDS, bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/realtime", tags=["realtime"])


@router.get("/stream")
async def stream(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    auth_user_id = await get_auth_principal(credentials)  # 401 on bad token
    agent = await get_agent_context(auth_user_id, db)  # 403 if not an agent
    await db.rollback()  # release the pooled connection for the stream's life

    return StreamingResponse(
        sse_generator(agent.organization_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def sse_generator(organization_id: UUID) -> AsyncIterator[bytes]:
    """The SSE byte stream for one organization (module-level: testable)."""
    queue = bus.subscribe(organization_id)
    logger.info("sse_open", extra={"organization_id": str(organization_id)})
    try:
        yield b": connected\n\n"
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                yield (f"event: {event['type']}\ndata: {json.dumps(event['payload'])}\n\n").encode()
            except TimeoutError:
                yield b": ping\n\n"
    finally:
        bus.unsubscribe(organization_id, queue)
        logger.info("sse_close", extra={"organization_id": str(organization_id)})

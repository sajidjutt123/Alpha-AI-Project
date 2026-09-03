"""Conversation agent contract — implemented by the Phase 5 pipeline.

The worker (app.workers.messaging) calls `respond()` with the tenant-bound
session, the lead, and the full history; the agent persists whatever it
needs (requirement updates, scoring, ai_runs telemetry, system notes) and
returns the reply text — or None for "say nothing" (engine unconfigured,
LLM failure, or a state where silence is correct). Business rules —
scoring, persistence, tool execution — live in services, never inside an
implementation of this protocol.
"""

import logging
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, Message

logger = logging.getLogger(__name__)


class ConversationAgent(Protocol):
    async def respond(
        self, session: AsyncSession, lead: Lead, history: Sequence[Message]
    ) -> str | None:
        """Produce (and persist side-effects of) the next outbound reply."""
        ...  # pragma: no cover


class UnconfiguredAgent:
    """Placeholder when no LLM is configured: logs and stays silent."""

    async def respond(
        self, session: AsyncSession, lead: Lead, history: Sequence[Message]
    ) -> str | None:
        logger.warning(
            "ai_engine_not_configured",
            extra={
                "lead_id": str(lead.id),
                "hint": "Set OPENAI_API_KEY to enable the conversation pipeline",
            },
        )
        return None

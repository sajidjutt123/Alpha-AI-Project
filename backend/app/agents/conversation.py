"""Conversation agent — the seam Phase 5 fills with the LangGraph pipeline.

The worker (app.workers.messaging) calls `respond()` with the lead and full
history; the agent returns the reply text (or None for "say nothing", e.g.
human handoff already in progress). Business rules — scoring, persistence,
tool execution — live in services, never inside an implementation of this
protocol.
"""

import logging
from collections.abc import Sequence
from typing import Protocol

from app.models import Lead, Message

logger = logging.getLogger(__name__)


class ConversationAgent(Protocol):
    async def respond(self, lead: Lead, history: Sequence[Message]) -> str | None:
        """Produce the next outbound reply for the conversation."""
        ...  # pragma: no cover


class UnconfiguredAgent:
    """Placeholder until Phase 5: logs and stays silent."""

    async def respond(self, lead: Lead, history: Sequence[Message]) -> str | None:
        logger.warning(
            "ai_engine_not_configured",
            extra={
                "lead_id": str(lead.id),
                "hint": "Phase 5 wires OpenAI + LangGraph here",
            },
        )
        return None

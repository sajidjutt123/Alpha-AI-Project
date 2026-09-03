"""Conversation pipeline (plan §6): analyze -> apply -> score -> reply.

Orchestration lives here; intelligence is bounded:
- The LLM produces STRUCTURED, Pydantic-validated facts and reply text.
- Business rules (scoring, handoff, status transitions) are deterministic
  Python — the model never decides them.
- Every LLM call is recorded in ai_runs (model, prompt version, tokens,
  latency) for cost analysis.
- Failures degrade gracefully: analysis/reply errors log and return None
  (no reply sent); the webhook has already acked, a later retry or human
  picks it up.
"""

import json
import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import LLMProvider
from app.agents.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    PROMPT_VERSION,
    REPLY_SYSTEM_PROMPT,
    build_analysis_user_prompt,
    build_reply_user_prompt,
)
from app.core.config import get_settings
from app.models import Lead, Message
from app.models.enums import LeadIntent, LeadStatus, MessageChannel, SenderType
from app.repositories import AIRunRepository, LeadRepository, MessageRepository
from app.schemas.ai import ConversationAnalysis, Sentiment
from app.services.scoring import ScoringService

logger = logging.getLogger(__name__)

HANDOFF_REPLY = (
    "Of course — I'm connecting you with one of our property experts right away. "
    "They'll continue here shortly. 🙌"
)
MAX_REPLY_CHARS = 800


class ConversationPipelineAgent:
    """Implements the ConversationAgent protocol (see workers.messaging)."""

    def __init__(
        self,
        provider: LLMProvider,
        scoring: ScoringService | None = None,
    ) -> None:
        self.provider = provider
        settings = get_settings()
        self.scoring = scoring or ScoringService(
            hot_threshold=settings.score_threshold_hot,
            warm_threshold=settings.score_threshold_warm,
        )
        self.history_window = settings.ai_history_window

    # -- public entrypoint ----------------------------------------------------
    async def respond(
        self, session: AsyncSession, lead: Lead, history: Sequence[Message]
    ) -> str | None:
        try:
            analysis = await self._analyze(session, lead, history)
        except Exception:
            logger.exception("ai_analysis_failed", extra={"lead_id": str(lead.id)})
            return None

        await self._apply_analysis(session, lead, analysis, history)

        needs_human = (
            analysis.intent == LeadIntent.HUMAN_AGENT or analysis.sentiment == Sentiment.FRUSTRATED
        )
        if needs_human:
            await MessageRepository(session).add_message(
                lead_id=lead.id,
                sender_type=SenderType.SYSTEM,
                content=f"AI handed off to a human agent (intent={analysis.intent.value}, "
                f"sentiment={analysis.sentiment.value})",
                channel=MessageChannel.DASHBOARD,
            )
            await self._mark_contacted(lead)
            return HANDOFF_REPLY

        try:
            reply = await self._generate_reply(session, lead, history, analysis)
        except Exception:
            logger.exception("ai_reply_failed", extra={"lead_id": str(lead.id)})
            return None

        if reply is None or not (1 <= len(reply) <= MAX_REPLY_CHARS):
            logger.error("ai_reply_invalid", extra={"lead_id": str(lead.id)})
            return None
        await self._mark_contacted(lead)
        return reply

    # -- steps ------------------------------------------------------------------
    async def _analyze(
        self, session: AsyncSession, lead: Lead, history: Sequence[Message]
    ) -> ConversationAnalysis:
        result = await self.provider.complete(
            system=ANALYSIS_SYSTEM_PROMPT,
            user=build_analysis_user_prompt(lead, history, window=self.history_window),
            # Provider-side strict schemas are best-effort; the authoritative
            # contract is documented in prompts.analysis_json_schema() and
            # enforced right here by Pydantic regardless of provider.
            schema=None,
        )
        await AIRunRepository(session).record(
            lead_id=lead.id,
            model=result.model,
            prompt_version=f"{PROMPT_VERSION}:analysis",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
        )
        return ConversationAnalysis.model_validate(json.loads(result.content))

    async def _apply_analysis(
        self,
        session: AsyncSession,
        lead: Lead,
        analysis: ConversationAnalysis,
        history: Sequence[Message],
    ) -> None:
        customer_messages = sum(1 for m in history if m.sender_type == SenderType.CUSTOMER)
        # Apply extracted facts first, then score the UPDATED lead so the
        # qualification reflects this turn's information.
        await LeadRepository(session).update_fields(
            lead,
            intent=analysis.intent,
            budget_min=analysis.budget_min,
            budget_max=analysis.budget_max,
            preferred_location=analysis.preferred_location,
            property_type=analysis.property_type,
            bedrooms=analysis.bedrooms,
            urgency_score=analysis.urgency_score,
        )
        breakdown = self.scoring.score(lead, customer_messages)
        lead.qualification_score = breakdown.total
        logger.info(
            "lead_scored",
            extra={
                "lead_id": str(lead.id),
                "score": breakdown.total,
                "temperature": breakdown.temperature.value,
            },
        )

    async def _generate_reply(
        self,
        session: AsyncSession,
        lead: Lead,
        history: Sequence[Message],
        analysis: ConversationAnalysis,
    ) -> str | None:
        result = await self.provider.complete(
            system=REPLY_SYSTEM_PROMPT,
            user=build_reply_user_prompt(lead, history, analysis, window=self.history_window),
        )
        await AIRunRepository(session).record(
            lead_id=lead.id,
            model=result.model,
            prompt_version=f"{PROMPT_VERSION}:reply",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
        )
        return result.content.strip()

    async def _mark_contacted(self, lead: Lead) -> None:
        if lead.status == LeadStatus.NEW:
            lead.status = LeadStatus.CONTACTED


def build_conversation_agent() -> ConversationPipelineAgent | None:
    """Wire the pipeline from settings; None when no LLM is configured."""
    from app.agents.llm import build_provider

    provider = build_provider()
    if provider is None:
        return None
    return ConversationPipelineAgent(provider)


__all__ = ["HANDOFF_REPLY", "ConversationPipelineAgent", "build_conversation_agent"]

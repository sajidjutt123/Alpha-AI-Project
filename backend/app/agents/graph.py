"""LangGraph conversation workflow (plan Day 13).

    START → analyze → apply ─┬─(handoff)→ handoff → END
                             └─(reply)──→ match → reply → END

State flows through LangGraph; nodes are closures over the tenant-bound
session, the LLM provider, and the deterministic services (scoring,
matching, tools). The LLM appears only where language is needed (analysis,
reply) — routing, scoring, matching, and persistence stay deterministic.

Built per message (per job) because the session/tenant are request-scoped;
compilation is cheap and no checkpointer is used (state stays in memory).
"""

import json
import logging
from collections.abc import Sequence
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import LLMProvider
from app.agents.prompts import (
    PROMPT_VERSION,
    build_analysis_user_prompt,
    build_reply_user_prompt,
)
from app.agents.tools import ToolError, ToolExecutor
from app.core.config import get_settings
from app.models import Lead, Message
from app.models.enums import LeadIntent, LeadStatus, MessageChannel, SenderType
from app.repositories import AIRunRepository, LeadRepository, MessageRepository
from app.schemas.ai import ConversationAnalysis, Sentiment
from app.services.matching import MatchingService
from app.services.scoring import ScoringService

logger = logging.getLogger(__name__)

HANDOFF_REPLY = (
    "Of course — I'm connecting you with one of our property experts right away. "
    "They'll continue here shortly. 🙌"
)
MAX_REPLY_CHARS = 800


class ConversationState(TypedDict, total=False):
    lead: Lead
    history: Sequence[Message]
    analysis: ConversationAnalysis
    customer_messages: int
    needs_handoff: bool
    recommendations: list[dict[str, Any]]
    reply: str | None
    error: bool


def build_conversation_graph(
    session: AsyncSession,
    provider: LLMProvider,
    *,
    scoring: ScoringService | None = None,
    matching: MatchingService | None = None,
    history_window: int | None = None,
) -> Any:
    """Compile the workflow bound to one session/tenant and provider."""
    settings = get_settings()
    scoring = scoring or ScoringService(
        hot_threshold=settings.score_threshold_hot,
        warm_threshold=settings.score_threshold_warm,
    )
    matching = matching or MatchingService()
    window = history_window or settings.ai_history_window
    runs = AIRunRepository(session)
    leads = LeadRepository(session)
    messages = MessageRepository(session)

    # -- nodes ---------------------------------------------------------------

    async def analyze(state: ConversationState) -> ConversationState:
        lead: Lead = state["lead"]
        history: Sequence[Message] = state["history"]
        result = await provider.complete(
            system=_analysis_system(),
            user=build_analysis_user_prompt(lead, history, window=window),
        )
        await runs.record(
            lead_id=lead.id,
            model=result.model,
            prompt_version=f"{PROMPT_VERSION}:analysis",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
        )
        analysis = ConversationAnalysis.model_validate(json.loads(result.content))
        return {"analysis": analysis}

    async def apply(state: ConversationState) -> ConversationState:
        lead: Lead = state["lead"]
        history: Sequence[Message] = state["history"]
        analysis: ConversationAnalysis = state["analysis"]

        customer_messages = sum(1 for m in history if m.sender_type == SenderType.CUSTOMER)
        # Apply extracted facts first, then score the UPDATED lead.
        await leads.update_fields(
            lead,
            intent=analysis.intent,
            budget_min=analysis.budget_min,
            budget_max=analysis.budget_max,
            preferred_location=analysis.preferred_location,
            property_type=analysis.property_type,
            bedrooms=analysis.bedrooms,
            urgency_score=analysis.urgency_score,
        )
        breakdown = scoring.score(lead, customer_messages)
        lead.qualification_score = breakdown.total
        logger.info(
            "lead_scored",
            extra={
                "lead_id": str(lead.id),
                "score": breakdown.total,
                "temperature": breakdown.temperature.value,
            },
        )
        return {
            "customer_messages": customer_messages,
            "needs_handoff": (
                analysis.intent == LeadIntent.HUMAN_AGENT
                or analysis.sentiment == Sentiment.FRUSTRATED
            ),
        }

    async def handoff(state: ConversationState) -> ConversationState:
        lead: Lead = state["lead"]
        analysis: ConversationAnalysis = state["analysis"]
        await messages.add_message(
            lead_id=lead.id,
            sender_type=SenderType.SYSTEM,
            content=f"AI handed off to a human agent (intent={analysis.intent.value}, "
            f"sentiment={analysis.sentiment.value})",
            channel=MessageChannel.DASHBOARD,
        )
        _mark_contacted(lead)
        return {"reply": HANDOFF_REPLY}

    async def match(state: ConversationState) -> ConversationState:
        lead: Lead = state["lead"]
        if not matching.ready(lead):
            # Not enough preferences yet — ask, don't recommend.
            return {"recommendations": None}  # type: ignore[typeddict-item]

        executor = ToolExecutor(session, lead.organization_id)
        try:
            # Deterministic tool use through the validated choke point.
            await executor.execute("search_properties", {"limit": 20})
            matches = await matching.find_and_persist(session, lead)
        except ToolError:
            logger.exception("tool_failed", extra={"lead_id": str(lead.id)})
            matches = []
        recommendations = [
            {
                "id": str(item.property.id),
                "title": item.property.title,
                "location": item.property.location,
                "price": item.property.price,
                "bedrooms": item.property.bedrooms,
                "match_score": item.score,
                "reason": item.reason,
            }
            for item in matches
        ]
        return {"recommendations": recommendations}

    async def reply(state: ConversationState) -> ConversationState:
        lead: Lead = state["lead"]
        history: Sequence[Message] = state["history"]
        analysis: ConversationAnalysis = state["analysis"]
        recommendations = state.get("recommendations")

        result = await provider.complete(
            system=_reply_system(),
            user=build_reply_user_prompt(
                lead, history, analysis, window=window, recommendations=recommendations
            ),
        )
        await runs.record(
            lead_id=lead.id,
            model=result.model,
            prompt_version=f"{PROMPT_VERSION}:reply",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
        )
        text = result.content.strip()
        if not (1 <= len(text) <= MAX_REPLY_CHARS):
            logger.error("ai_reply_invalid", extra={"lead_id": str(lead.id)})
            return {"reply": None}
        _mark_contacted(lead)
        return {"reply": text}

    def route_after_apply(state: ConversationState) -> str:
        return "handoff" if state.get("needs_handoff") else "match"

    # -- graph ---------------------------------------------------------------

    graph = StateGraph(ConversationState)
    graph.add_node("analyze", analyze)
    graph.add_node("apply", apply)
    graph.add_node("handoff", handoff)
    graph.add_node("match", match)
    graph.add_node("reply", reply)
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "apply")
    graph.add_conditional_edges(
        "apply", route_after_apply, {"handoff": "handoff", "match": "match"}
    )
    graph.add_edge("handoff", END)
    graph.add_edge("match", "reply")
    graph.add_edge("reply", END)
    return graph.compile()


def _mark_contacted(lead: Lead) -> None:
    if lead.status == LeadStatus.NEW:
        lead.status = LeadStatus.CONTACTED


def _analysis_system() -> str:
    from app.agents.prompts import ANALYSIS_SYSTEM_PROMPT

    return ANALYSIS_SYSTEM_PROMPT


def _reply_system() -> str:
    from app.agents.prompts import REPLY_SYSTEM_PROMPT

    return REPLY_SYSTEM_PROMPT


class ConversationPipelineAgent:
    """ConversationAgent implementation backed by the LangGraph workflow."""

    def __init__(
        self,
        provider: LLMProvider,
        scoring: ScoringService | None = None,
        matching: MatchingService | None = None,
    ) -> None:
        self.provider = provider
        self.scoring = scoring
        self.matching = matching

    async def respond(
        self, session: AsyncSession, lead: Lead, history: Sequence[Message]
    ) -> str | None:
        try:
            graph = build_conversation_graph(
                session,
                self.provider,
                scoring=self.scoring,
                matching=self.matching,
            )
            final: ConversationState = await graph.ainvoke(
                {"lead": lead, "history": list(history)},
                config={"recursion_limit": 10},
            )
        except Exception:  # worker must survive any pipeline error
            logger.exception("ai_pipeline_failed", extra={"lead_id": str(lead.id)})
            return None
        return final.get("reply")


def build_conversation_agent() -> ConversationPipelineAgent | None:
    """Wire the workflow from settings; None when no LLM is configured."""
    from app.agents.llm import build_provider

    provider = build_provider()
    if provider is None:
        return None
    return ConversationPipelineAgent(provider)


__all__ = [
    "HANDOFF_REPLY",
    "ConversationPipelineAgent",
    "build_conversation_agent",
    "build_conversation_graph",
]

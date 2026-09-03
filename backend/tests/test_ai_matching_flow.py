"""Graph integration: recommendations flow into grounded replies (Phase 6)."""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import ConversationPipelineAgent
from app.core.database import with_tenant
from app.models import Lead, LeadPropertyMatch, Message
from app.models.enums import MessageChannel, SenderType
from tests.conftest import OrgContext
from tests.fakes import ScriptedLLM, analysis_result, reply_result

REPLY_CALL = 1


def history_for(lead: Lead, *texts: str) -> list[Message]:
    return [
        Message(
            lead_id=lead.id,
            sender_type=SenderType.CUSTOMER,
            content=text,
            channel=MessageChannel.WHATSAPP,
        )
        for text in texts
    ]


async def run(
    db_session: AsyncSession, org: OrgContext, llm: ScriptedLLM, lead: Lead, history: list[Message]
) -> str | None:
    agent = ConversationPipelineAgent(llm)
    async with with_tenant(db_session, org.org.id):
        return await agent.respond(db_session, lead, history)


def buyer_payload() -> dict[str, Any]:
    return {
        "intent": "BUY",
        "budget_min": 20_000_000,
        "budget_max": 32_000_000,
        "preferred_location": "DHA Lahore",
        "property_type": "HOUSE",
        "bedrooms": 4,
        "urgency_score": 7,
        "sentiment": "POSITIVE",
    }


class TestRecommendationFlow:
    async def test_match_persisted_and_grounds_reply(
        self, db_session: AsyncSession, org_context: OrgContext
    ) -> None:
        lead = org_context.leads[3]
        llm = ScriptedLLM(
            analysis_result(buyer_payload()),
            reply_result(
                "Great news — I found a 5 Marla designer house in DHA Phase 6 at "
                "PKR 3.25 crore within your budget. Would you like to visit it this week?"
            ),
        )

        reply = await run(
            db_session,
            org_context,
            llm,
            lead,
            history_for(lead, "Need a 4 bed house in DHA under 3.2 crore"),
        )

        assert reply is not None and "DHA Phase 6" in reply

        # the reply prompt was grounded in the tool-sourced recommendation
        reply_prompt = llm.calls[REPLY_CALL]["user"]
        assert "RECOMMENDED PROPERTIES" in reply_prompt
        assert "DHA Phase 6 House" in reply_prompt
        assert "32,500,000" in reply_prompt

        # and the match is persisted with score + reason
        async with with_tenant(db_session, org_context.org.id):
            rows = (
                (
                    await db_session.execute(
                        select(LeadPropertyMatch).where(LeadPropertyMatch.lead_id == lead.id)
                    )
                )
                .scalars()
                .all()
            )
            snapshots = [(r.match_score, r.reason) for r in rows]
            await db_session.rollback()
        assert len(snapshots) == 1
        score, reason = snapshots[0]
        assert score >= 50
        assert reason

    async def test_no_match_prompts_honest_fallback(
        self, db_session: AsyncSession, org_context: OrgContext
    ) -> None:
        lead = org_context.leads[3]
        llm = ScriptedLLM(
            analysis_result(
                {**buyer_payload(), "budget_min": 200_000_000, "budget_max": 300_000_000}
            ),
            reply_result(
                "I couldn't find anything in that range right now — shall I look at "
                "a slightly higher area or adjust the budget?"
            ),
        )

        reply = await run(
            db_session, org_context, llm, lead, history_for(lead, "budget 20-30 crore")
        )

        assert reply is not None and "couldn't find" in reply
        prompt = llm.calls[REPLY_CALL]["user"]
        assert "none matched" in prompt

        async with with_tenant(db_session, org_context.org.id):
            rows = (
                (
                    await db_session.execute(
                        select(LeadPropertyMatch).where(LeadPropertyMatch.lead_id == lead.id)
                    )
                )
                .scalars()
                .all()
            )
            await db_session.rollback()
        assert rows == []

    async def test_insufficient_requirements_skips_matching(
        self, db_session: AsyncSession, org_context: OrgContext
    ) -> None:
        lead = org_context.leads[3]
        llm = ScriptedLLM(
            analysis_result({"intent": "BUY"}),  # nothing concrete yet
            reply_result("Happy to help! Which area of Lahore are you looking at?"),
        )

        reply = await run(db_session, org_context, llm, lead, history_for(lead, "hi"))

        assert reply is not None
        prompt = llm.calls[REPLY_CALL]["user"]
        assert "not specific enough" in prompt

        async with with_tenant(db_session, org_context.org.id):
            rows = (
                (
                    await db_session.execute(
                        select(LeadPropertyMatch).where(LeadPropertyMatch.lead_id == lead.id)
                    )
                )
                .scalars()
                .all()
            )
            await db_session.rollback()
        assert rows == []


class TestGraphRouting:
    async def test_handoff_short_circuits_matching(
        self, db_session: AsyncSession, org_context: OrgContext
    ) -> None:
        """HUMAN_AGENT routes analyze→apply→handoff: no match/reply LLM calls."""
        from app.agents.graph import HANDOFF_REPLY

        lead = org_context.leads[3]
        llm = ScriptedLLM(analysis_result({**buyer_payload(), "intent": "HUMAN_AGENT"}))

        reply = await run(db_session, org_context, llm, lead, history_for(lead, "agent please"))

        assert reply == HANDOFF_REPLY
        assert len(llm.calls) == 1

        async with with_tenant(db_session, org_context.org.id):
            rows = (
                (
                    await db_session.execute(
                        select(LeadPropertyMatch).where(LeadPropertyMatch.lead_id == lead.id)
                    )
                )
                .scalars()
                .all()
            )
            await db_session.rollback()
        assert rows == []


@pytest.mark.parametrize(
    ("ceiling", "expected"),
    [(32_500_000, [100]), (27_500_000, [])],  # in range vs gated (18% over)
)
async def test_deterministic_scores_via_graph(
    db_session: AsyncSession, org_context: OrgContext, ceiling: int, expected: list[int]
) -> None:
    """End-to-end: extraction -> scoring -> matching all deterministic."""
    lead = org_context.leads[3]
    llm = ScriptedLLM(
        analysis_result({**buyer_payload(), "budget_max": ceiling}),
        reply_result("I found a matching house — shall I share details?"),
    )
    await run(db_session, org_context, llm, lead, history_for(lead, "looking"))

    async with with_tenant(db_session, org_context.org.id):
        matches = (
            (
                await db_session.execute(
                    select(LeadPropertyMatch).where(LeadPropertyMatch.lead_id == lead.id)
                )
            )
            .scalars()
            .all()
        )
        snapshots = [m.match_score for m in matches]
        await db_session.rollback()
    assert snapshots == expected

"""AI agent orchestration (Phase 5/6: LangGraph workflow).

Pipeline (plan §6): intent detection -> information extraction ->
qualification -> property search -> business rules -> response generation ->
validation. The LLM never writes to the database directly; it calls
validated tools implemented by services.

Until Phase 5 lands, `UnconfiguredAgent` occupies the seam so the webhook
pipeline (Phase 4) is fully wired and testable end-to-end.
"""

from app.agents.conversation import ConversationAgent, UnconfiguredAgent

__all__ = ["ConversationAgent", "UnconfiguredAgent"]

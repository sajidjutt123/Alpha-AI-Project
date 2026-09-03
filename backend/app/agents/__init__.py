"""AI agent orchestration (Phases 5/6).

Pipeline (plan §6, implemented in `pipeline.py`): intent detection ->
information extraction -> lead qualification (deterministic scoring) ->
[Phase 6: property search tool] -> business rules -> response generation ->
validation. The LLM never writes to the database directly; it calls
validated tools implemented by services.

Modules:
- `llm`        provider abstraction (OpenAI REST + protocol for fakes)
- `prompts`    versioned prompts (PROMPT_VERSION tracked in ai_runs)
- `pipeline`   ConversationPipelineAgent — orchestrates analyze/apply/reply
- `conversation` the ConversationAgent protocol + UnconfiguredAgent fallback
"""

from app.agents.conversation import ConversationAgent, UnconfiguredAgent
from app.agents.pipeline import (
    HANDOFF_REPLY,
    ConversationPipelineAgent,
    build_conversation_agent,
)

__all__ = [
    "HANDOFF_REPLY",
    "ConversationAgent",
    "ConversationPipelineAgent",
    "UnconfiguredAgent",
    "build_conversation_agent",
]

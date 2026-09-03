"""AI agent orchestration (Phases 5/6).

LangGraph workflow (plan §6 + Day 13), implemented in `graph.py`:

    START → analyze → apply ─┬─(handoff)→ handoff → END
                             └─(reply)──→ match → reply → END

- `analyze` (LLM): intent + requirement extraction, Pydantic-validated
- `apply`: requirements persisted, deterministic qualification scoring
- `handoff`: HUMAN_AGENT / FRUSTRATED → deterministic human takeover
- `match`: validated tools (`tools.py`) + deterministic matching service
- `reply` (LLM): grounded in tool results — never invents listings

The LLM appears only where language is needed. Modules:
- `llm`          provider abstraction (OpenAI REST + protocol for fakes)
- `prompts`      versioned prompts (PROMPT_VERSION tracked in ai_runs)
- `tools`        ToolExecutor — validated choke point for AI tool requests
- `graph`        the LangGraph workflow + ConversationPipelineAgent
- `conversation` the ConversationAgent protocol + UnconfiguredAgent fallback
"""

from app.agents.conversation import ConversationAgent, UnconfiguredAgent
from app.agents.graph import (
    HANDOFF_REPLY,
    ConversationPipelineAgent,
    build_conversation_agent,
    build_conversation_graph,
)

__all__ = [
    "HANDOFF_REPLY",
    "ConversationAgent",
    "ConversationPipelineAgent",
    "UnconfiguredAgent",
    "build_conversation_agent",
    "build_conversation_graph",
]

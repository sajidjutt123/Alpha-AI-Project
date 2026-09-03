"""Test doubles for the AI engine (implement the LLMProvider protocol)."""

from typing import Any

from app.agents.llm import LLMResult


class ScriptedLLM:
    """Returns queued results in order; records every prompt it received."""

    def __init__(self, *results: LLMResult) -> None:
        self.queue = list(results)
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
    ) -> LLMResult:
        self.calls.append({"system": system, "user": user, "schema": schema})
        if not self.queue:
            raise AssertionError("ScriptedLLM ran out of queued results")
        return self.queue.pop(0)

    @property
    def last_user_prompt(self) -> str:
        return self.calls[-1]["user"]


class FailingLLM:
    """Always raises — exercises graceful degradation."""

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
    ) -> LLMResult:
        raise RuntimeError("llm provider unavailable")


def analysis_result(payload: dict[str, Any], **usage: int) -> LLMResult:
    import json

    return LLMResult(
        content=json.dumps(payload),
        model="scripted-test-model",
        input_tokens=usage.get("input_tokens", 100),
        output_tokens=usage.get("output_tokens", 50),
        latency_ms=usage.get("latency_ms", 200),
    )


def reply_result(text: str, **usage: int) -> LLMResult:
    return LLMResult(
        content=text,
        model="scripted-test-model",
        input_tokens=usage.get("input_tokens", 150),
        output_tokens=usage.get("output_tokens", 60),
        latency_ms=usage.get("latency_ms", 300),
    )

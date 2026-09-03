"""LLM provider abstraction (plan: "AI service abstraction").

One protocol, two implementations:
- `OpenAIProvider` — chat completions via REST (httpx2), JSON-schema
  structured outputs for the analysis step, usage + latency captured.
- test/scripted fakes implement the same protocol (see tests/fakes.py).

The provider knows nothing about leads, tools, or the database — the
pipeline orchestrates, the provider only completes text.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx2 as httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResult:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
    ) -> LLMResult:
        """Run one completion. `schema` requests strict JSON output."""
        ...  # pragma: no cover


class OpenAIProvider:
    """OpenAI chat completions with optional strict JSON schema output."""

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
    ) -> LLMResult:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "strict": True, "schema": schema},
            }

        started = time.perf_counter()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=45,
            )
            response.raise_for_status()
            payload = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)

        usage = payload.get("usage", {})
        return LLMResult(
            content=payload["choices"][0]["message"]["content"] or "",
            model=payload.get("model", self.model),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            latency_ms=latency_ms,
        )


def build_provider() -> OpenAIProvider | None:
    """Return the configured provider, or None when no API key is set."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
    )

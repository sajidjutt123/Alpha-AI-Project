"""AI run telemetry repository (cost analysis & debugging, plan §5)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRun
from app.repositories.base import BaseRepository


class AIRunRepository(BaseRepository[AIRun]):
    model = AIRun

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def record(
        self,
        *,
        lead_id: UUID,
        model: str,
        prompt_version: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> AIRun:
        return await self.add(
            AIRun(
                lead_id=lead_id,
                model=model,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        )

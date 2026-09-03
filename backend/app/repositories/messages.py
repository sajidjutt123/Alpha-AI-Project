"""Message repository — conversation transcript access."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, MessageChannel, SenderType
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def add_message(
        self,
        *,
        lead_id: uuid.UUID,
        sender_type: SenderType,
        content: str,
        channel: MessageChannel,
        external_message_id: str | None = None,
    ) -> Message:
        return await self.add(
            Message(
                lead_id=lead_id,
                sender_type=sender_type,
                content=content,
                channel=channel,
                external_message_id=external_message_id,
            )
        )

    async def list_for_lead(self, lead_id: uuid.UUID, *, limit: int = 200) -> Sequence[Message]:
        """Conversation history, oldest first."""
        stmt = (
            select(Message)
            .where(Message.lead_id == lead_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_external_id(self, external_message_id: str) -> Message | None:
        result = await self.session.execute(
            select(Message).where(Message.external_message_id == external_message_id)
        )
        return result.scalar_one_or_none()

"""Message model — one row per conversational turn."""

import uuid

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UuidPkMixin
from app.models.enums import MessageChannel, SenderType


class Message(UuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "messages"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    sender_type: Mapped[SenderType] = mapped_column(
        Enum(SenderType, name="sender_type", create_type=False, native_enum=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[MessageChannel] = mapped_column(
        Enum(MessageChannel, name="message_channel", create_type=False, native_enum=True),
        nullable=False,
    )
    external_message_id: Mapped[str | None] = mapped_column(
        String,
        unique=True,  # Twilio SID — idempotent webhook processing
    )

    def __repr__(self) -> str:
        return f"Message(id={self.id!r}, sender={self.sender_type!r}, channel={self.channel!r})"

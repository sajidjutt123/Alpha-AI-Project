"""Outbound messaging via Twilio (WhatsApp/SMS).

Two implementations behind one protocol:
- `TwilioRestSender` — thin async REST client against the Twilio Messages
  API (chosen when account credentials are configured).
- `ConsoleSender` — development fallback that logs instead of sending, so
  the full pipeline runs locally without credentials.

The platform-level credentials serve all organizations in V1; per-org
Twilio subaccounts are a V2 concern.
"""

import logging
from typing import Protocol
from uuid import uuid4

import httpx2 as httpx

from app.core.config import get_settings
from app.models.enums import MessageChannel

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01/Accounts"


def _with_channel_prefix(number: str, channel: MessageChannel) -> str:
    """Twilio WhatsApp addresses carry the whatsapp: prefix; SMS does not."""
    if channel == MessageChannel.WHATSAPP and not number.startswith("whatsapp:"):
        return f"whatsapp:{number}"
    return number


class MessageSender(Protocol):
    async def send(self, *, to: str, body: str, channel: MessageChannel) -> str:
        """Deliver a message; returns the provider message id (Sid)."""
        ...  # pragma: no cover


class TwilioRestSender:
    """Sends via the Twilio Messages REST API (async)."""

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        # Transport seam: tests inject a MockTransport instead of the network.
        self._transport = transport

    async def send(self, *, to: str, body: str, channel: MessageChannel) -> str:
        settings = get_settings()
        from_number = (
            settings.twilio_whatsapp_from
            if channel == MessageChannel.WHATSAPP
            else settings.twilio_sms_from
        )
        if not from_number:
            raise RuntimeError(f"No outbound {channel.value} number configured")

        url = f"{TWILIO_API_BASE}/{self.account_sid}/Messages.json"
        data = {
            "To": _with_channel_prefix(to, channel),
            "From": from_number,
            "Body": body,
        }
        async with httpx.AsyncClient(
            auth=(self.account_sid, self.auth_token), timeout=10, transport=self._transport
        ) as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            return str(response.json()["sid"])


class ConsoleSender:
    """Development sender — logs the message and returns a fake Sid."""

    async def send(self, *, to: str, body: str, channel: MessageChannel) -> str:
        logger.info(
            "console_message_sent",
            extra={"to": to, "channel": channel.value, "body": body},
        )
        return f"console-{uuid4().hex[:12]}"


def build_sender() -> MessageSender:
    """Pick the sender from configuration (Twilio creds or console)."""
    settings = get_settings()
    if settings.twilio_account_sid and settings.twilio_auth_token:
        return TwilioRestSender(settings.twilio_account_sid, settings.twilio_auth_token)
    return ConsoleSender()

"""Outbound Twilio REST sender tests (Phase 9 audit).

The send path carries credentials and talks to the network — it gets exact
assertions on URL, auth, payload shape, channel prefixes, and error
behaviour, using an injected transport (no network, no real credentials).
"""

import base64

import httpx2 as httpx
import pytest

from app.core.config import get_settings
from app.models.enums import MessageChannel
from app.services.twilio import TWILIO_API_BASE, TwilioRestSender, build_sender

ACCOUNT_SID = "AC" + "a1" * 16
AUTH_TOKEN = "0123456789abcdef0123456789abcdef"


def make_sender(
    handler,
    monkeypatch: pytest.MonkeyPatch,
    *,
    whatsapp_from: str | None = "whatsapp:+14155238886",
    sms_from: str | None = "+14155238887",
) -> TwilioRestSender:
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", whatsapp_from or "")
    monkeypatch.setenv("TWILIO_SMS_FROM", sms_from or "")
    get_settings.cache_clear()
    return TwilioRestSender(ACCOUNT_SID, AUTH_TOKEN, transport=httpx.MockTransport(handler))


class TestTwilioRestSender:
    async def test_whatsapp_send_hits_expected_endpoint_with_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json={"sid": "SMtest123"})

        sender = make_sender(handler, monkeypatch)
        sid = await sender.send(
            to="+923001234567", body="Salam! Confirming Saturday.", channel=MessageChannel.WHATSAPP
        )

        assert sid == "SMtest123"
        request = seen[0]
        # exact account-scoped Messages endpoint
        assert str(request.url) == f"{TWILIO_API_BASE}/{ACCOUNT_SID}/Messages.json"
        # HTTP Basic auth = account sid + auth token, nothing else
        expected = base64.b64encode(f"{ACCOUNT_SID}:{AUTH_TOKEN}".encode()).decode()
        assert request.headers["Authorization"] == f"Basic {expected}"
        # whatsapp prefix applied to To, org number in From
        body = request.read().decode()
        assert "To=whatsapp%3A%2B923001234567" in body
        assert "From=whatsapp%3A%2B14155238886" in body
        assert "Body=Salam%21+Confirming+Saturday." in body

    async def test_sms_send_has_no_whatsapp_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json={"sid": "SMsms456"})

        sender = make_sender(handler, monkeypatch)
        sid = await sender.send(to="+923001234567", body="Plot details", channel=MessageChannel.SMS)
        assert sid == "SMsms456"
        assert "To=%2B923001234567" in seen[0].read().decode()

    async def test_missing_outbound_number_is_a_hard_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            return httpx.Response(200)

        sender = make_sender(handler, monkeypatch, whatsapp_from=None, sms_from=None)
        with pytest.raises(RuntimeError, match="No outbound"):
            await sender.send(to="+923001234567", body="x", channel=MessageChannel.SMS)

    async def test_provider_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"message": "Authenticate"})

        sender = make_sender(handler, monkeypatch)
        with pytest.raises(httpx.HTTPStatusError):
            await sender.send(to="+923001234567", body="x", channel=MessageChannel.WHATSAPP)


class TestBuildSender:
    def test_console_sender_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        get_settings.cache_clear()
        sender = build_sender()
        assert type(sender).__name__ == "ConsoleSender"

    def test_rest_sender_with_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", ACCOUNT_SID)
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", AUTH_TOKEN)
        get_settings.cache_clear()
        assert isinstance(build_sender(), TwilioRestSender)
        get_settings.cache_clear()

"""Twilio webhook signature validation.

Twilio signs every webhook request: X-Twilio-Signature is base64(HMAC-SHA1(
AuthToken, full_request_url + concat(sorted_params))). We validate with a
constant-time comparison. See Twilio docs "Secure your webhooks".
"""

import base64
import hashlib
import hmac

from fastapi import Request


def compute_signature(url: str, params: dict[str, str], token: str) -> str:
    """Twilio's signature algorithm (used for validation and tests)."""
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def validate_signature(request: Request, form: dict[str, str], signature: str, token: str) -> bool:
    """Validate the signature against the request URL and form params.

    `TWILIO_WEBHOOK_URL` (settings) overrides the URL used in validation —
    required when running behind a proxy where the internally visible URL
    differs from the public one Twilio called.
    """
    from app.core.config import get_settings

    override = get_settings().twilio_webhook_url
    url = override or str(request.url)
    expected = compute_signature(url, form, token)
    return hmac.compare_digest(expected, signature)

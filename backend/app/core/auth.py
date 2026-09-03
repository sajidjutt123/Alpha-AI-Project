"""JWT authentication primitives.

Tokens are Supabase Auth JWTs (HS256 with the project's JWT secret — the
"legacy" secret available in every Supabase dashboard). For local
development and tests, the same code path verifies tokens signed with
`AUTH_DEV_SECRET`.

RS256/JWKS verification is a deployment-time option (Phase 10) — the
verification seam is this module only.
"""

import jwt
from pydantic import BaseModel

from app.core.config import get_settings


class Principal(BaseModel):
    """The verified token claims we trust."""

    auth_user_id: str


def decode_token(token: str) -> Principal:
    """Verify signature/expiry and return the caller's principal.

    Raises `jwt.InvalidTokenError` for any malformed, tampered, or expired
    token — callers translate that to HTTP 401.
    """
    settings = get_settings()
    secret = settings.supabase_jwt_secret or settings.auth_dev_secret
    if not secret:
        raise RuntimeError(
            "No JWT secret configured: set SUPABASE_JWT_SECRET "
            "(production) or AUTH_DEV_SECRET (development)"
        )
    claims = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        options={"require": ["exp", "sub"]},
        leeway=10,
    )
    return Principal(auth_user_id=str(claims["sub"]))


def issue_dev_token(auth_user_id: str, secret: str, *, expires_in: int = 3600) -> str:
    """Mint a development/test token (never used in production paths)."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "sub": auth_user_id,
            "role": "authenticated",
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
        },
        secret,
        algorithm="HS256",
    )

"""JWT authentication primitives.

Verification strategies, tried in order (first success wins):

1. **JWKS (RS256/ES256)** — Supabase's asymmetric signing keys, published at
   `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (or an explicit
   `SUPABASE_JWKS_URL`). Newer Supabase projects sign access tokens with
   rotating asymmetric keys; the client caches the keyset and refreshes on
   unknown `kid` (PyJWKClient).
2. **HS256 shared secret** — the Supabase "legacy" JWT secret
   (`SUPABASE_JWT_SECRET`), for projects still on symmetric signing.
3. **Dev secret** — `AUTH_DEV_SECRET`, development/test only. Tokens are
   minted by tests via `app.core.auth.issue_dev_token`.

All strategies require `exp` + `sub` and share a 10s leeway. A token that
fails every configured strategy raises `jwt.InvalidTokenError` → HTTP 401.
Algorithm confusion is structurally impossible: each attempt pins its own
algorithm list, so an RS256 token can never verify against an HS secret
(and vice versa).
"""

import functools
from typing import Any

import jwt
from pydantic import BaseModel

from app.core.config import get_settings


class Principal(BaseModel):
    """The verified token claims we trust."""

    auth_user_id: str


def _verify_hs256(token: str, secret: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        options={"require": ["exp", "sub"]},
        leeway=10,
    )


def _jwks_url() -> str | None:
    settings = get_settings()
    if settings.supabase_jwks_url:
        return settings.supabase_jwks_url
    if settings.supabase_url:
        return f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return None


@functools.lru_cache(maxsize=4)
def _jwks_client_for(url: str) -> jwt.PyJWKClient:
    # PyJWKClient caches the fetched keyset and re-fetches only on unknown
    # `kid`, so per-request verification costs no network round-trip.
    return jwt.PyJWKClient(url, cache_keys=True)


def _verify_jwks(token: str, url: str) -> dict[str, Any]:
    client = _jwks_client_for(url)
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        options={"require": ["exp", "sub"]},
        leeway=10,
    )


def decode_token(token: str) -> Principal:
    """Verify signature/expiry and return the caller's principal.

    Raises `jwt.InvalidTokenError` for any malformed, tampered, or expired
    token — callers translate that to HTTP 401. The last strategy's error is
    re-raised so failures stay diagnosable.
    """
    settings = get_settings()
    error: jwt.InvalidTokenError = jwt.InvalidTokenError(
        "No JWT verification strategy configured: set SUPABASE_URL (JWKS), "
        "SUPABASE_JWT_SECRET, or AUTH_DEV_SECRET"
    )

    url = _jwks_url()
    if url is not None:
        try:
            claims = _verify_jwks(token, url)
            return Principal(auth_user_id=str(claims["sub"]))
        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
            # PyJWKClientError (keyset unreachable / unknown kid) must surface
            # as an auth failure (401), not an unhandled error (500).
            error = jwt.InvalidTokenError(f"jwks verification failed: {exc}")

    if settings.supabase_jwt_secret:
        try:
            claims = _verify_hs256(token, settings.supabase_jwt_secret)
            return Principal(auth_user_id=str(claims["sub"]))
        except jwt.InvalidTokenError as exc:
            error = exc

    if settings.auth_dev_secret:
        try:
            claims = _verify_hs256(token, settings.auth_dev_secret)
            return Principal(auth_user_id=str(claims["sub"]))
        except jwt.InvalidTokenError as exc:
            error = exc

    raise error


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

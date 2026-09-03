"""JWT verification strategy tests (Phase 10): JWKS/RS256 + HS256 + dev.

RS256 tokens are minted with a locally generated RSA key; the JWKS client is
stubbed with the matching public key (no network). Algorithm-confusion and
key-substitution attempts must fail closed.
"""

import uuid
from types import SimpleNamespace
from typing import Any

import jwt
import pytest

from app.core import auth as auth_module
from app.core.auth import decode_token, issue_dev_token
from app.core.config import get_settings
from tests.conftest import TEST_AUTH_SECRET

RSA_KEY = None  # generated lazily; cryptography lives in the dev env only


def rsa_keypair():
    global RSA_KEY
    if RSA_KEY is None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        RSA_KEY = (
            private.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            private.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
        )
    return RSA_KEY


def make_rs256_token(claims: dict[str, Any], *, kid: str = "test-key-1") -> str:
    from datetime import UTC, datetime, timedelta

    private_pem, _ = rsa_keypair()
    payload = {
        "sub": str(uuid.uuid4()),
        "iat": datetime.now(tz=UTC),
        "exp": datetime.now(tz=UTC) + timedelta(hours=1),
        **claims,
    }
    return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": kid})


def make_forged_hs256_with_public_key(kid: str = "test-key-1") -> str:
    """Hand-craft the classic alg-confusion token: HS256 signature where the
    verifier is expected to use the RSA public key (PyJWT refuses to mint
    this itself — InvalidKeyError — so the attack payload is assembled
    manually, exactly as an attacker would).
    """
    import base64
    import hashlib
    import hmac as hmac_module
    import json
    from datetime import UTC, datetime

    _, public_pem = rsa_keypair()

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "kid": kid}).encode())
    claims = b64(
        json.dumps(
            {
                "sub": str(uuid.uuid4()),
                "exp": int(datetime.now(tz=UTC).timestamp()) + 3600,
            }
        ).encode()
    )
    signature = hmac_module.new(public_pem, f"{header}.{claims}".encode(), hashlib.sha256).digest()
    return f"{header}.{claims}.{b64(signature)}"


def make_foreign_rsa_key() -> bytes:
    """A genuinely independent RSA public key (not the cached test key)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def stub_jwks(monkeypatch: pytest.MonkeyPatch, *, kid: str = "test-key-1") -> None:
    """Point the JWKS strategy at a keyset holding our test public key."""
    _, public_pem = rsa_keypair()

    class StubClient:
        def get_signing_key_from_jwt(self, token: str) -> Any:
            header = jwt.get_unverified_header(token)
            if header.get("kid") != kid:
                raise jwt.PyJWKClientError(f"unknown kid {header.get('kid')!r}")
            return SimpleNamespace(key=public_pem)

    monkeypatch.setattr(auth_module, "_jwks_client_for", lambda url: StubClient())


def enable_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWKS_URL", "https://stub.example/jwks.json")
    get_settings.cache_clear()
    auth_module._jwks_client_for.cache_clear()


class TestJwksStrategy:
    def test_rs256_token_verifies_via_jwks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        enable_jwks(monkeypatch)
        stub_jwks(monkeypatch)
        sub = str(uuid.uuid4())
        token = make_rs256_token({"sub": sub})
        assert decode_token(token).auth_user_id == sub

    def test_expired_rs256_token_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from datetime import UTC, datetime, timedelta

        enable_jwks(monkeypatch)
        stub_jwks(monkeypatch)
        private_pem, _ = rsa_keypair()
        token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "exp": datetime.now(tz=UTC) - timedelta(minutes=5),
            },
            private_pem,
            algorithm="RS256",
            headers={"kid": "test-key-1"},
        )
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token)

    def test_unknown_kid_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        enable_jwks(monkeypatch)
        stub_jwks(monkeypatch)
        token = make_rs256_token({"sub": str(uuid.uuid4())}, kid="attacker-key")
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token)

    def test_hs256_token_cannot_ride_the_jwks_strategy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Algorithm confusion: an HS256 token signed with the public key
        material must not verify (the strategy pins RS256/ES256)."""
        enable_jwks(monkeypatch)
        stub_jwks(monkeypatch)
        token = make_forged_hs256_with_public_key()
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token)

    def test_wrong_rsa_key_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        enable_jwks(monkeypatch)
        # JWKS holds our published key…
        stub_jwks(monkeypatch)
        # …but the token is signed by a different, attacker-generated key.
        token = make_rs256_token({"sub": str(uuid.uuid4())})
        other_public = make_foreign_rsa_key()
        monkeypatch.setattr(
            auth_module,
            "_jwks_client_for",
            lambda url: SimpleNamespace(
                get_signing_key_from_jwt=lambda t: SimpleNamespace(key=other_public)
            ),
        )
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token)


class TestStrategyPrecedence:
    def test_dev_secret_still_works_without_jwks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
        get_settings.cache_clear()
        token = issue_dev_token(str(uuid.uuid4()), TEST_AUTH_SECRET)
        assert decode_token(token)  # dev strategy (conftest sets AUTH_DEV_SECRET)

    def test_jwks_failure_falls_through_to_hs256(self, monkeypatch: pytest.MonkeyPatch) -> None:
        enable_jwks(monkeypatch)
        stub_jwks(monkeypatch)
        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_AUTH_SECRET)
        get_settings.cache_clear()
        # RS256 kid unknown to the stub → jwks strategy fails → HS256 verifies
        token = issue_dev_token(str(uuid.uuid4()), TEST_AUTH_SECRET)
        assert decode_token(token)

    def test_no_strategy_configured_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        monkeypatch.delenv("AUTH_DEV_SECRET", raising=False)
        get_settings.cache_clear()
        with pytest.raises(jwt.InvalidTokenError, match="No JWT verification strategy"):
            decode_token("whatever")

    def test_jwks_url_derived_from_supabase_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co")
        monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
        get_settings.cache_clear()
        assert auth_module._jwks_url() == "https://demo.supabase.co/auth/v1/.well-known/jwks.json"

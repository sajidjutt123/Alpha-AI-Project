"""Application configuration via environment variables.

All settings are read from the environment (12-factor). A root `.env` file is
honoured for local development; in production values come from the platform
(Railway/Render) or `docker-compose.yml`.

Secrets must never be committed — see `.env.example` at the repository root.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    """Central application settings."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App -----------------------------------------------------------------
    app_name: str = "Alpha AI"
    environment: Environment = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # CORS: origins allowed to call the API directly (the dashboard normally
    # goes through its own server-side proxy, but browsers/tools may hit this).
    allowed_origins: list[str] = ["http://localhost:3000"]

    # --- Security hardening (Phase 9) -----------------------------------------
    # Sliding-window rate limits, requests per minute per client IP.
    # 0 disables. In-process by design; Redis swap documented in
    # docs/security-audit.md (F1).
    dev_login_rate_limit: int = 10
    webhook_rate_limit: int = 240
    # Reject requests whose declared Content-Length exceeds this (bytes).
    max_request_body_bytes: int = 1_048_576  # 1 MiB

    # --- Database (Phase 2: Supabase / local Postgres) -----------------------
    # Runtime role (`alpha_app`, least privilege, subject to RLS).
    database_url: str = "postgresql+asyncpg://alpha_app:alpha_app@localhost:5432/alpha_ai"
    # Admin role (owner/superuser) — migrations and seeding only.
    admin_database_url: str | None = None
    # Password interpolated into the alpha_app role DDL by the migration runner.
    app_db_password: str = "alpha_app"

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    # Supabase Auth JWT secret ("legacy" secret in the dashboard) — production.
    supabase_jwt_secret: str | None = None
    # Development/test token secret — used only when the Supabase secret is
    # absent. Tokens are minted by tests via `app.core.auth.issue_dev_token`.
    auth_dev_secret: str | None = None

    # --- Twilio (Phase 4: WhatsApp/SMS webhooks) -----------------------------
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None  # e.g. "whatsapp:+14155238886"
    twilio_sms_from: str | None = None  # e.g. "+14155238886"
    # Public webhook URL if the internally visible URL differs (proxies).
    twilio_webhook_url: str | None = None
    # Fallback organization for shared-number deployments (sandbox/single
    # tenant); when set, unroutable `To` numbers land in this organization.
    default_organization_slug: str | None = None

    # --- OpenAI (Phase 5: AI engine) ------------------------------------------
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    # Conversation memory: most recent N messages included in prompts.
    ai_history_window: int = 20
    # Lead scoring classification thresholds (plan: 80/50).
    score_threshold_hot: int = 80
    score_threshold_warm: int = 50
    # Property matching (Phase 6): minimum score to count as a match, and
    # how many recommendations to surface per turn.
    match_score_threshold: int = 50
    match_recommendation_limit: int = 3

    # --- Redis (Phase 8+: queue for async AI processing; optional) -----------
    redis_url: str | None = None

    # --- Observability (Phase 10: Sentry) -------------------------------------
    sentry_dsn: str | None = None

    @property
    def debug(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()

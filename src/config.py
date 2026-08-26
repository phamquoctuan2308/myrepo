from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = ""
    cors_origin_regex: str = ""

    # LLM
    llm_provider: Literal["google", "groq", "openai"] = "google"
    google_api_key: str = ""
    groq_api_key: str = ""
    openai_api_key: str = ""
    model_name: str = "gemini-2.5-flash"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    daily_token_budget: int = Field(default=200_000, ge=0)
    agent_max_thread_messages: int = Field(default=20, ge=6, le=100)
    agent_thread_summary_chars: int = Field(default=6000, ge=1000, le=20000)
    agent_thread_retention_days: int = Field(default=30, ge=1, le=365)

    # Enterprise default: organizations are provisioned by platform operations.
    # Keep this switch only for local/demo compatibility and isolated tests.
    allow_self_service_organization_creation: bool = False

    # Agent context engineering. Fractions are budgets for optional/retrieved layers, not a claim
    # that every model or turn must consume exactly these percentages. System/policy and output
    # reserve are protected; lower-value retrieval is trimmed first.
    agent_context_window_tokens: int = Field(default=32_768, ge=8_192)
    agent_output_reserve_tokens: int = Field(default=4_096, ge=512)
    memory_short_term_fraction: float = Field(default=0.10, ge=0.02, le=0.50)
    memory_long_term_fraction: float = Field(default=0.04, ge=0.01, le=0.20)
    memory_episodic_fraction: float = Field(default=0.03, ge=0.0, le=0.20)
    memory_retrieval_fraction: float = Field(default=0.03, ge=0.0, le=0.30)
    memory_heartbeat_interval_seconds: int = Field(default=900, ge=60)
    memory_compaction_message_threshold: int = Field(default=24, ge=8)
    memory_recent_messages_to_keep: int = Field(default=12, ge=4)
    # Token budget for injecting a Conversation's rolling summary into the prompt (see
    # conversation_summary_service.py) - separate from conversation_summary_max_chars below, which
    # caps what's stored in the DB, not what's re-fit into any one prompt.
    memory_conversation_summary_fraction: float = Field(default=0.03, ge=0.0, le=0.20)

    # Consent-scoped rolling summary for 1-1/group Conversation chats (conversation_summary_service.py).
    conversation_summary_enabled: bool = True
    conversation_summary_threshold_messages: int = Field(default=30, ge=1)
    conversation_summary_batch_size: int = Field(default=60, ge=1, le=500)
    conversation_summary_max_chars: int = Field(default=12_000, ge=500)
    conversation_summary_interval_seconds: int = Field(default=900, ge=60)
    conversation_summary_sweep_limit: int = Field(default=10, ge=1, le=100)

    # Database
    database_url: str = "sqlite:///./data/app.db"
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=200)
    db_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)

    # Auth
    secret_key: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    initial_admin_email: str = ""
    bootstrap_owner_user_id: str = ""
    # Alternative to initial_admin_email for bootstrapping the first admin from the separate
    # Frontend/admin app's own registration screen (POST /auth/admin/register) instead of
    # pre-deciding an email address - only usable while no admin account exists yet.
    admin_bootstrap_key: str = ""
    # "Sign in with Google" - Web application OAuth Client ID (audience for ID-token verification).
    # Distinct from the per-user Calendar OAuth client below. No client secret is needed here:
    # this setting only verifies Google Sign-In ID tokens.
    google_oauth_client_id: str = ""

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # Google Calendar
    google_calendar_client_id: str = ""
    google_calendar_client_secret: str = ""
    google_calendar_redirect_uri: str = "http://localhost:8000/api/v1/calendar/oauth/callback"
    credential_encryption_key: str = ""
    frontend_origin: str = "http://localhost:5173"
    calendar_timezone: str = "Asia/Ho_Chi_Minh"

    # Reminders / scheduler
    scheduler_timezone: str = "Asia/Ho_Chi_Minh"

    # Calendar polling (no public HTTPS URL yet for Google's real push/webhook channels, so
    # changes made directly in Google Calendar are picked up by polling with a syncToken instead)
    calendar_poll_interval_seconds: int = Field(default=20, ge=5)

    # Per-process burst protection. The deployment is intentionally single-worker because
    # WebSocket connections and the scheduler are process-local.
    rate_limit_enabled: bool = True
    rate_limit_auth: str = "10/minute"
    rate_limit_register: str = "5/minute"
    rate_limit_chat: str = "15/minute"
    rate_limit_crud: str = "60/minute"

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.app_env != "production":
            return self
        if len(self.secret_key.encode("utf-8")) < 32 or "change-me" in self.secret_key:
            raise ValueError("SECRET_KEY must contain at least 32 bytes of non-placeholder data in production")
        if self.database_url.startswith("sqlite"):
            raise ValueError("Production requires PostgreSQL; SQLite is supported only for development and tests")
        origins = {origin.strip() for origin in self.cors_origins.split(",") if origin.strip()}
        if not origins or "*" in origins:
            raise ValueError("CORS_ORIGINS must explicitly list trusted origins in production")
        if self.cors_origin_regex:
            raise ValueError("CORS_ORIGIN_REGEX must be empty in production; list trusted origins explicitly")
        if self.llm_provider == "google" and not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google in production")
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq in production")
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

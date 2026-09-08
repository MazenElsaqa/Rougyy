"""
Centralized application configuration.

Loaded once from environment variables / .env via pydantic-settings.
No secrets are hard-coded here (Rule: "No hard-coded keys").
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "sqlite:///./data/concert_singer.sqlite"

    # --- Gemini (used starting Phase 5) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # --- Query execution (Phase 3 timeout) ---
    query_timeout_ms: int = 5000

    # --- Tracing (Phase 1) ---
    otel_service_name: str = "ai-database-agent"
    otel_traces_exporter: str = "console"
    otel_exporter_otlp_endpoint: str | None = None

    # --- App ---
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton for the process)."""
    return Settings()

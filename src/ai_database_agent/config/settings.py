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

    # --- LLM: OpenAI-compatible SDK (Phase 5+) ---
    # Set LLM_PROVIDER=ollama for a local Ollama server. The legacy
    # OPENAI_* variables remain supported for hosted OpenAI-compatible APIs.
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    # Optional override: chat model used only for answer phrasing.
    # Falls back to ollama_model when unset, so existing setups keep working.
    ollama_answer_model: str | None = None
    llm_model: str = "gpt-4o"
    # Optional override for hosted OpenAI-compatible providers.
    llm_answer_model: str | None = None

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

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
    # Works with any provider that supports the OpenAI API interface:
    #   OpenAI:  base_url=None (default), api_key=sk-...
    #   Gemini:  base_url="https://generativelanguage.googleapis.com/v1beta/openai/", api_key=AIza...
    #   Ollama:  base_url="http://localhost:11434/v1", api_key="ollama"
    # Ollama is the local-first default so the project works without a paid API account.
    openai_api_key: str = "ollama"
    openai_base_url: str | None = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5-coder:7b"

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

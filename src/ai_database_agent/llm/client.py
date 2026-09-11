"""
OpenAI-compatible LLM client (Phase 5, wired up as part of Milestone 1).

Works with any provider exposing the OpenAI chat-completions
interface: OpenAI itself, Gemini's OpenAI-compatible endpoint, or a
local Ollama server. Configured entirely from Settings/.env — no
hard-coded keys or base URLs. See .env.example for provider switches.
"""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import urljoin

import httpx
from openai import OpenAI

from ai_database_agent.config import get_settings


def _ollama_openai_url(base_url: str) -> str:
    """Normalize an Ollama host to the OpenAI-compatible API path."""
    return urljoin(f"{base_url.rstrip('/')}/", "v1/").rstrip("/")


def llm_model_name() -> str:
    """SQL-generation model (coder). Kept as the default entry point."""
    settings = get_settings()
    return settings.ollama_model if settings.llm_provider.lower() == "ollama" else settings.llm_model


def llm_sql_model_name() -> str:
    """Explicit alias for the SQL-generation model."""
    return llm_model_name()


def llm_answer_model_name() -> str:
    """Answer-phrasing model (chat). Falls back to the SQL model when unset."""
    settings = get_settings()
    if settings.llm_provider.lower() == "ollama":
        return settings.ollama_answer_model or settings.ollama_model
    return settings.llm_answer_model or settings.llm_model


def llm_connection_info() -> dict[str, str]:
    """Return the effective provider configuration without exposing secrets."""
    settings = get_settings()
    if settings.llm_provider.lower() == "ollama":
        return {
            "provider": "ollama",
            "model": settings.ollama_model,
            "sql_model": settings.ollama_model,
            "answer_model": settings.ollama_answer_model or settings.ollama_model,
            "base_url": _ollama_openai_url(settings.ollama_base_url),
        }
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "sql_model": settings.llm_model,
        "answer_model": settings.llm_answer_model or settings.llm_model,
        "base_url": settings.openai_base_url or "https://api.openai.com/v1",
    }


@lru_cache
def get_llm_client() -> OpenAI:
    """Return a cached OpenAI-compatible client for the selected provider."""
    settings = get_settings()
    if settings.llm_provider.lower() == "ollama":
        return OpenAI(api_key="ollama", base_url=_ollama_openai_url(settings.ollama_base_url))
    return OpenAI(api_key=settings.openai_api_key or "unset", base_url=settings.openai_base_url)


def check_ollama_connection() -> tuple[bool, str]:
    """Check that Ollama is reachable and the configured model(s) are installed."""
    settings = get_settings()
    if settings.llm_provider.lower() != "ollama":
        return True, "Ollama is not the selected provider."
    try:
        response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
        models = {model.get("name", "") for model in response.json().get("models", [])}

        def _installed(configured: str) -> bool:
            return configured in models or any(
                name.split(":", 1)[0] == configured.split(":", 1)[0] for name in models
            )

        required = {settings.ollama_model}
        if settings.ollama_answer_model:
            required.add(settings.ollama_answer_model)
        missing = [m for m in required if not _installed(m)]
        if missing:
            return False, f"Model(s) {missing} not installed. Run: ollama pull {missing[0]}"
        return True, "Ollama is reachable and the configured model(s) are installed."
    except httpx.HTTPError:
        return False, f"Cannot reach Ollama at {settings.ollama_base_url}. Run: ollama serve"

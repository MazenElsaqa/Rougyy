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
    settings = get_settings()
    return settings.ollama_model if settings.llm_provider.lower() == "ollama" else settings.llm_model


def llm_connection_info() -> dict[str, str]:
    """Return the effective provider configuration without exposing secrets."""
    settings = get_settings()
    if settings.llm_provider.lower() == "ollama":
        return {
            "provider": "ollama",
            "model": settings.ollama_model,
            "base_url": _ollama_openai_url(settings.ollama_base_url),
        }
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
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
    """Check that Ollama is reachable and the configured model is installed."""
    settings = get_settings()
    if settings.llm_provider.lower() != "ollama":
        return True, "Ollama is not the selected provider."
    try:
        response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
        models = {model.get("name", "") for model in response.json().get("models", [])}
        configured = settings.ollama_model
        installed = configured in models or any(name.split(":", 1)[0] == configured.split(":", 1)[0] for name in models)
        if not installed:
            return False, f"Model '{configured}' is not installed. Run: ollama pull {configured}"
        return True, "Ollama is reachable and the configured model is installed."
    except httpx.HTTPError:
        return False, f"Cannot reach Ollama at {settings.ollama_base_url}. Run: ollama serve"

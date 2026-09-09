"""
OpenAI-compatible LLM client (Phase 5, wired up as part of Milestone 1).

Works with any provider exposing the OpenAI chat-completions
interface: OpenAI itself, Gemini's OpenAI-compatible endpoint, or a
local Ollama server. Configured entirely from Settings/.env — no
hard-coded keys or base URLs. See .env.example for provider switches.
"""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from ai_database_agent.config import get_settings


@lru_cache
def get_llm_client() -> OpenAI:
    """Return a process-wide cached OpenAI-compatible client built from settings."""
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key or "unset", base_url=settings.openai_base_url)

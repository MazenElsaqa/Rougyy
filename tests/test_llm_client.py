from ai_database_agent.config import get_settings
from ai_database_agent.llm.client import (
    _ollama_openai_url,
    llm_answer_model_name,
    llm_connection_info,
    llm_model_name,
)


def test_ollama_url_adds_v1_path(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    assert _ollama_openai_url("http://localhost:11434") == "http://localhost:11434/v1"


def test_ollama_uses_ollama_model(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
    assert llm_model_name() == "qwen2.5:3b"
    assert llm_connection_info()["provider"] == "ollama"
    get_settings.cache_clear()


def test_openai_uses_legacy_model(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    assert llm_model_name() == "custom-model"
    get_settings.cache_clear()


def test_ollama_answer_model_falls_back_to_sql_model(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    # .env file sets OLLAMA_ANSWER_MODEL, so override with empty to simulate unset
    # (falsy values fall back to the SQL model in llm_answer_model_name()).
    monkeypatch.setenv("OLLAMA_ANSWER_MODEL", "")
    assert llm_answer_model_name() == "qwen2.5-coder:7b"
    assert llm_connection_info()["answer_model"] == "qwen2.5-coder:7b"
    get_settings.cache_clear()


def test_ollama_answer_model_override(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    monkeypatch.setenv("OLLAMA_ANSWER_MODEL", "qwen3.5:4b-mlx")
    assert llm_model_name() == "qwen2.5-coder:7b"
    assert llm_answer_model_name() == "qwen3.5:4b-mlx"
    assert llm_connection_info()["answer_model"] == "qwen3.5:4b-mlx"
    get_settings.cache_clear()

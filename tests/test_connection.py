from sqlalchemy import text

from ai_database_agent.database.connection import get_engine


def test_get_engine_returns_working_connection(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/_smoke_test.sqlite")
    # Settings is cached; clear caches so the monkeypatched env var takes effect.
    from ai_database_agent.config.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1

    get_settings.cache_clear()
    get_engine.cache_clear()

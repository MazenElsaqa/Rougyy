"""
Reusable SQLAlchemy connection (Phase 1, section 6.1).

A single Engine is created from settings.database_url and reused
across the app. Kept deliberately minimal for Phase 1: no pooling
tuning, no multi-DB abstraction yet (that's Phase 42+, DatabaseExecutor).
"""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from ai_database_agent.config import get_settings
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)


@lru_cache
def get_engine() -> Engine:
    """Return a cached SQLAlchemy Engine built from the configured database URL."""
    with _tracer.start_as_current_span("db.create_engine") as span:
        settings = get_settings()
        span.set_attribute("db.url_scheme", settings.database_url.split(":")[0])
        engine = create_engine(settings.database_url, future=True)
        return engine

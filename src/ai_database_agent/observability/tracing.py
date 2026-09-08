"""
Tracing bootstrap (Phase 1 / [NEW] per spec v2).

Introduced now, on purpose, so every phase built after this one is
traceable from day one instead of retrofitting observability at
Phase 21. Uses a console exporter for local dev; nothing sensitive
is ever put into span attributes (no chain-of-thought, no secrets).

Usage:
    from ai_database_agent.observability.tracing import setup_tracing, get_tracer

    setup_tracing()  # call once, e.g. at app/CLI startup
    tracer = get_tracer(__name__)

    with tracer.start_as_current_span("db.connect"):
        ...
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from ai_database_agent.config import get_settings

_INITIALIZED = False


def setup_tracing() -> None:
    """
    Configure the global TracerProvider exactly once per process.

    Exporter choice is driven by settings.otel_traces_exporter:
      - "console" (default): prints spans to stdout, good enough for
        local dev / Phase 1 and does not require any external collector.
      - "otlp": exports to settings.otel_exporter_otlp_endpoint, for
        when a real collector (Jaeger, Tempo, etc.) is wired up later.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    settings = get_settings()

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    if settings.otel_traces_exporter == "otlp" and settings.otel_exporter_otlp_endpoint:
        # Imported lazily: the OTLP exporter package is an optional extra
        # and shouldn't be a hard dependency for local/dev-only usage.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        exporter = ConsoleSpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _INITIALIZED = True


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for `name` (typically __name__ of the calling module)."""
    if not _INITIALIZED:
        setup_tracing()
    return trace.get_tracer(name)

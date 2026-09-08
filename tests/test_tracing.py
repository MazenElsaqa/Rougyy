from opentelemetry import trace

from ai_database_agent.observability.tracing import get_tracer, setup_tracing


def test_setup_tracing_is_idempotent():
    setup_tracing()
    provider_first = trace.get_tracer_provider()
    setup_tracing()
    provider_second = trace.get_tracer_provider()
    assert provider_first is provider_second


def test_get_tracer_returns_usable_tracer():
    tracer = get_tracer("test.module")
    with tracer.start_as_current_span("test-span") as span:
        assert span is not None

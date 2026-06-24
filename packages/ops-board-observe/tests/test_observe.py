from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
import pytest

from ops_board_observe import observe
from ops_board_observe.instrumentation import _otlp_signal_endpoint, _reset_for_tests


def test_otlp_signal_endpoint_adds_signal_suffix() -> None:
    assert _otlp_signal_endpoint("http://hp-15:4318", "traces") == "http://hp-15:4318/v1/traces"
    assert _otlp_signal_endpoint("http://hp-15:4318/", "logs") == "http://hp-15:4318/v1/logs"
    assert _otlp_signal_endpoint("http://hp-15:4318/v1/traces", "traces") == "http://hp-15:4318/v1/traces"


def test_observe_emits_success_span_with_common_custom_and_duration_attributes() -> None:
    exporter = _configure_in_memory_tracing()

    @observe("unit.success", attributes={"unit.custom": "yes", "unit.count": 2, "unit.ok": True})
    def add(left: int, right: int) -> int:
        return left + right

    assert add(2, 3) == 5

    span = _only_span(exporter)
    assert span.name == "unit.success"
    assert span.attributes["code.function"].endswith(".add")
    assert span.attributes["code.namespace"] == __name__
    assert span.attributes["unit.custom"] == "yes"
    assert span.attributes["unit.count"] == 2
    assert span.attributes["unit.ok"] is True
    assert span.attributes["ops_board.duration_ms"] >= 0
    assert span.status.status_code is StatusCode.OK


def test_observe_records_one_exception_event_and_error_status() -> None:
    exporter = _configure_in_memory_tracing()

    @observe("unit.failure")
    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        fail()

    span = _only_span(exporter)
    exception_events = [event for event in span.events if event.name == "exception"]
    assert len(exception_events) == 1
    assert span.status.status_code is StatusCode.ERROR


@pytest.mark.asyncio
async def test_observe_supports_async_functions() -> None:
    exporter = _configure_in_memory_tracing()

    @observe("unit.async")
    async def async_add(left: int, right: int) -> int:
        return left + right

    assert await async_add(2, 4) == 6

    span = _only_span(exporter)
    assert span.name == "unit.async"
    assert span.status.status_code is StatusCode.OK


@pytest.mark.asyncio
async def test_observe_records_one_async_exception_event_and_error_status() -> None:
    exporter = _configure_in_memory_tracing()

    @observe("unit.async_failure")
    async def fail() -> None:
        raise RuntimeError("async boom")

    with pytest.raises(RuntimeError, match="async boom"):
        await fail()

    span = _only_span(exporter)
    exception_events = [event for event in span.events if event.name == "exception"]
    assert len(exception_events) == 1
    assert span.status.status_code is StatusCode.ERROR


def _configure_in_memory_tracing() -> InMemorySpanExporter:
    _reset_for_tests()
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


def _only_span(exporter: InMemorySpanExporter):
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    return spans[0]

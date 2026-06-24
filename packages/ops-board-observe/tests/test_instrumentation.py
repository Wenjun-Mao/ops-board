from __future__ import annotations

import logging
from collections.abc import Iterator

from opentelemetry import trace
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.sdk._logs.export import LogExportResult
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
import pytest

from ops_board_observe import bootstrap_observability, observe
import ops_board_observe.instrumentation as instrumentation
from ops_board_observe.instrumentation import _otlp_signal_endpoint, _reset_for_tests


@pytest.fixture(autouse=True)
def reset_observability() -> Iterator[None]:
    _reset_for_tests()
    _remove_otel_logging_handlers()
    yield
    _reset_for_tests()
    _remove_otel_logging_handlers()


def test_otlp_signal_endpoint_adds_signal_suffix() -> None:
    assert _otlp_signal_endpoint("http://hp-15:4318", "traces") == "http://hp-15:4318/v1/traces"
    assert _otlp_signal_endpoint("http://hp-15:4318/", "logs") == "http://hp-15:4318/v1/logs"
    assert _otlp_signal_endpoint("http://hp-15:4318/v1/traces", "traces") == "http://hp-15:4318/v1/traces"


def test_bootstrap_returns_settings_with_export_disabled() -> None:
    settings = bootstrap_observability(
        export=False,
        service_name="unit-service",
        service_namespace="unit-namespace",
        owner="unit-owner",
        otlp_endpoint="http://hp-15:4318",
    )

    assert settings.service_name == "unit-service"
    assert settings.service_namespace == "unit-namespace"
    assert settings.owner == "unit-owner"
    assert settings.otlp_endpoint == "http://hp-15:4318"


def test_bootstrap_export_false_does_not_attach_otel_logging_handler() -> None:
    bootstrap_observability(
        export=False,
        service_name="unit-service",
        service_namespace="unit-namespace",
        owner="unit-owner",
        otlp_endpoint="http://hp-15:4318",
    )

    assert _otel_logging_handlers() == []


def test_bootstrap_export_true_attaches_one_otel_logging_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_noop_otlp_exporters(monkeypatch)

    bootstrap_observability(
        export=True,
        service_name="unit-service",
        service_namespace="unit-namespace",
        owner="unit-owner",
        otlp_endpoint="http://hp-15:4318",
    )
    handlers = _otel_logging_handlers()
    assert len(handlers) == 1
    first_handler = handlers[0]

    bootstrap_observability(
        export=True,
        service_name="unit-service-2",
        service_namespace="unit-namespace",
        owner="unit-owner",
        otlp_endpoint="http://hp-15:4318",
    )
    assert _otel_logging_handlers() == [first_handler]

    _reset_for_tests()
    assert _otel_logging_handlers() == []

    bootstrap_observability(
        export=True,
        service_name="unit-service-3",
        service_namespace="unit-namespace",
        owner="unit-owner",
        otlp_endpoint="http://hp-15:4318",
    )
    handlers = _otel_logging_handlers()
    assert len(handlers) == 1
    assert handlers[0] is not first_handler


def test_bootstrap_export_true_enables_info_level_root_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_noop_otlp_exporters(monkeypatch)
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.WARNING)

    try:
        bootstrap_observability(
            export=True,
            service_name="unit-service",
            service_namespace="unit-namespace",
            owner="unit-owner",
            otlp_endpoint="http://hp-15:4318",
        )

        assert root_logger.getEffectiveLevel() <= logging.INFO
        assert logging.getLogger("ops_board_observe").isEnabledFor(logging.INFO)
    finally:
        root_logger.setLevel(original_level)


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


def _otel_logging_handlers() -> list[LoggingHandler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, LoggingHandler)
    ]


def _remove_otel_logging_handlers() -> None:
    root_logger = logging.getLogger()
    for handler in _otel_logging_handlers():
        root_logger.removeHandler(handler)


def _install_noop_otlp_exporters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(instrumentation, "OTLPSpanExporter", _NoopSpanExporter)
    monkeypatch.setattr(instrumentation, "OTLPLogExporter", _NoopLogExporter)


class _NoopSpanExporter:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def export(self, *args: object, **kwargs: object) -> SpanExportResult:
        return SpanExportResult.SUCCESS

    def shutdown(self, *args: object, **kwargs: object) -> None:
        return None

    def force_flush(self, *args: object, **kwargs: object) -> bool:
        return True


class _NoopLogExporter:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def export(self, *args: object, **kwargs: object) -> LogExportResult:
        return LogExportResult.SUCCESS

    def shutdown(self, *args: object, **kwargs: object) -> None:
        return None

    def force_flush(self, *args: object, **kwargs: object) -> bool:
        return True

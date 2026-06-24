from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import LogExportResult
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
import pytest

from ops_board_observe import bootstrap_observability, observe
import ops_board_observe.instrumentation as instrumentation
from ops_board_observe.instrumentation import _otlp_signal_endpoint, _reset_for_tests

BOOTSTRAP_OVERRIDES = {
    "service_name": "unit-service",
    "service_namespace": "unit-namespace",
    "owner": "unit-owner",
    "otlp_endpoint": "http://hp-15:4318",
}


@pytest.fixture(autouse=True)
def reset_observability() -> Iterator[None]:
    root_logger = logging.getLogger()
    original_root_level = root_logger.level
    _reset_for_tests()
    _remove_otel_logging_handlers()
    yield
    _reset_for_tests()
    _remove_otel_logging_handlers()
    root_logger.setLevel(original_root_level)


def test_otlp_signal_endpoint_adds_signal_suffix() -> None:
    assert _otlp_signal_endpoint("http://hp-15:4318", "traces") == "http://hp-15:4318/v1/traces"
    assert _otlp_signal_endpoint("http://hp-15:4318/", "logs") == "http://hp-15:4318/v1/logs"
    assert _otlp_signal_endpoint("http://hp-15:4318/v1/traces", "traces") == "http://hp-15:4318/v1/traces"


def test_bootstrap_returns_settings_with_export_disabled() -> None:
    settings = bootstrap_observability(
        export=False,
        **BOOTSTRAP_OVERRIDES,
    )

    assert settings.service_name == "unit-service"
    assert settings.service_namespace == "unit-namespace"
    assert settings.owner == "unit-owner"
    assert settings.otlp_endpoint == "http://hp-15:4318"


def test_bootstrap_export_false_does_not_attach_otel_logging_handler_or_change_root_level() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    bootstrap_observability(
        export=False,
        **BOOTSTRAP_OVERRIDES,
    )

    assert _otel_logging_handlers() == []
    assert root_logger.getEffectiveLevel() == logging.WARNING


def test_reset_shuts_down_export_enabled_batch_processor_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_noop_otlp_exporters(monkeypatch)

    bootstrap_observability(
        export=True,
        **BOOTSTRAP_OVERRIDES,
    )

    assert _otel_batch_processor_threads()

    _reset_for_tests()

    assert _wait_for_no_otel_batch_processor_threads()


def test_bootstrap_export_true_attaches_one_otel_logging_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_noop_otlp_exporters(monkeypatch)

    bootstrap_observability(
        export=True,
        **BOOTSTRAP_OVERRIDES,
    )
    handlers = _otel_logging_handlers()
    assert len(handlers) == 1
    first_handler = handlers[0]

    bootstrap_observability(
        export=True,
        service_name="unit-service",
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


def test_concurrent_identical_bootstrap_calls_share_one_active_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_slow_noop_otlp_exporters(monkeypatch)

    def call_bootstrap() -> object:
        return bootstrap_observability(
            export=True,
            **BOOTSTRAP_OVERRIDES,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        settings = list(executor.map(lambda _: call_bootstrap(), range(8)))

    assert all(setting is settings[0] for setting in settings)
    assert len(_otel_logging_handlers()) == 1


def test_bootstrap_export_false_then_export_true_raises_without_adding_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_noop_otlp_exporters(monkeypatch)

    bootstrap_observability(
        export=False,
        **BOOTSTRAP_OVERRIDES,
    )

    with pytest.raises(RuntimeError, match="already bootstrapped"):
        bootstrap_observability(
            export=True,
            **BOOTSTRAP_OVERRIDES,
        )

    assert _otel_logging_handlers() == []


def test_bootstrap_rejects_changed_settings_after_first_success() -> None:
    bootstrap_observability(
        export=False,
        **BOOTSTRAP_OVERRIDES,
    )

    with pytest.raises(RuntimeError, match="already bootstrapped"):
        bootstrap_observability(
            export=False,
            service_name="unit-service-2",
            service_namespace="unit-namespace",
            owner="unit-owner",
            otlp_endpoint="http://hp-15:4318",
        )


def test_bootstrap_rejects_external_preconfigured_tracer_provider() -> None:
    external_provider = TracerProvider()
    trace.set_tracer_provider(external_provider)

    with pytest.raises(RuntimeError, match="OpenTelemetry tracer provider"):
        bootstrap_observability(
            export=False,
            service_name="unit-service",
            service_namespace="unit-namespace",
            owner="unit-owner",
            otlp_endpoint="http://hp-15:4318",
        )

    assert instrumentation._BOOTSTRAPPED is False
    assert trace.get_tracer_provider() is external_provider


def test_bootstrap_rejects_external_preconfigured_logger_provider() -> None:
    external_provider = LoggerProvider()
    set_logger_provider(external_provider)

    with pytest.raises(RuntimeError, match="OpenTelemetry logger provider"):
        bootstrap_observability(
            export=False,
            service_name="unit-service",
            service_namespace="unit-namespace",
            owner="unit-owner",
            otlp_endpoint="http://hp-15:4318",
        )

    assert instrumentation._BOOTSTRAPPED is False
    assert get_logger_provider() is external_provider


def test_bootstrap_rolls_back_provider_globals_after_logging_handler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_noop_otlp_exporters(monkeypatch)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    original_attach_logging_handler = instrumentation._attach_logging_handler

    def fail_attach_logging_handler(logger_provider: LoggerProvider) -> None:
        raise RuntimeError("attach boom")

    monkeypatch.setattr(
        instrumentation,
        "_attach_logging_handler",
        fail_attach_logging_handler,
    )

    with pytest.raises(RuntimeError, match="attach boom"):
        bootstrap_observability(
            export=True,
            service_name="unit-service",
            service_namespace="unit-namespace",
            owner="unit-owner",
            otlp_endpoint="http://hp-15:4318",
        )

    assert instrumentation._BOOTSTRAPPED is False
    assert root_logger.getEffectiveLevel() == logging.WARNING

    monkeypatch.setattr(
        instrumentation,
        "_attach_logging_handler",
        original_attach_logging_handler,
    )

    settings = bootstrap_observability(
        export=True,
        service_name="unit-service",
        service_namespace="unit-namespace",
        owner="unit-owner",
        otlp_endpoint="http://hp-15:4318",
    )

    assert settings.service_name == "unit-service"
    assert len(_otel_logging_handlers()) == 1


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


def test_bootstrap_export_true_adds_only_otel_handler_when_root_has_no_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_noop_otlp_exporters(monkeypatch)
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    for handler in original_handlers:
        root_logger.removeHandler(handler)

    try:
        bootstrap_observability(
            export=True,
            service_name="unit-service",
            service_namespace="unit-namespace",
            owner="unit-owner",
            otlp_endpoint="http://hp-15:4318",
        )

        handlers = list(root_logger.handlers)
        assert len(handlers) == 1
        assert isinstance(handlers[0], LoggingHandler)
    finally:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            if handler not in original_handlers:
                handler.close()
        for handler in original_handlers:
            root_logger.addHandler(handler)


def test_bootstrap_resource_attributes_use_service_owner() -> None:
    bootstrap_observability(
        export=False,
        service_name="unit-service",
        service_namespace="unit-namespace",
        owner="unit-owner",
        otlp_endpoint="http://hp-15:4318",
    )
    provider = trace.get_tracer_provider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    @observe("unit.resource")
    def run() -> str:
        return "ok"

    assert run() == "ok"

    span = _only_span(exporter)
    assert span.resource.attributes["service.owner"] == "unit-owner"
    assert "ops_board.owner" not in span.resource.attributes


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


def _otel_batch_processor_threads() -> list[threading.Thread]:
    return [
        thread
        for thread in threading.enumerate()
        if thread.name in {"OtelBatchSpanRecordProcessor", "OtelBatchLogRecordProcessor"}
    ]


def _wait_for_no_otel_batch_processor_threads(timeout_seconds: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _otel_batch_processor_threads():
            return True
        time.sleep(0.01)
    return not _otel_batch_processor_threads()


def _install_noop_otlp_exporters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(instrumentation, "OTLPSpanExporter", _NoopSpanExporter)
    monkeypatch.setattr(instrumentation, "OTLPLogExporter", _NoopLogExporter)


def _install_slow_noop_otlp_exporters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(instrumentation, "OTLPSpanExporter", _SlowNoopSpanExporter)
    monkeypatch.setattr(instrumentation, "OTLPLogExporter", _SlowNoopLogExporter)


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


class _SlowNoopSpanExporter(_NoopSpanExporter):
    def __init__(self, *args: object, **kwargs: object) -> None:
        time.sleep(0.05)
        super().__init__(*args, **kwargs)


class _SlowNoopLogExporter(_NoopLogExporter):
    def __init__(self, *args: object, **kwargs: object) -> None:
        time.sleep(0.05)
        super().__init__(*args, **kwargs)

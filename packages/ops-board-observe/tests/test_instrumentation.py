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

from ops_board_observe import OpsBoardSettings, bootstrap_observability, observe
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
    settings = _bootstrap(export=False)

    assert settings.service_name == "unit-service"
    assert settings.service_namespace == "unit-namespace"
    assert settings.owner == "unit-owner"
    assert settings.otlp_endpoint == "http://hp-15:4318"


def test_bootstrap_export_false_does_not_attach_otel_logging_handler_or_change_root_level() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    _bootstrap(export=False)

    assert _otel_logging_handlers() == []
    assert root_logger.getEffectiveLevel() == logging.WARNING


def test_reset_shuts_down_export_enabled_batch_processor_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_noop_otlp_exporters(monkeypatch)

    _bootstrap(export=True)

    assert _otel_batch_processor_threads()

    _reset_for_tests()

    assert _wait_for_no_otel_batch_processor_threads()


def test_bootstrap_export_true_attaches_one_otel_logging_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_noop_otlp_exporters(monkeypatch)

    _bootstrap(export=True)
    handlers = _otel_logging_handlers()
    assert len(handlers) == 1
    first_handler = handlers[0]

    _bootstrap(export=True)
    assert _otel_logging_handlers() == [first_handler]

    _reset_for_tests()
    assert _otel_logging_handlers() == []

    _bootstrap(export=True, service_name="unit-service-3")
    handlers = _otel_logging_handlers()
    assert len(handlers) == 1
    assert handlers[0] is not first_handler


def test_concurrent_identical_bootstrap_calls_share_one_active_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_slow_noop_otlp_exporters(monkeypatch)

    def call_bootstrap() -> object:
        return _bootstrap(export=True)

    with ThreadPoolExecutor(max_workers=8) as executor:
        settings = list(executor.map(lambda _: call_bootstrap(), range(8)))

    assert all(setting is settings[0] for setting in settings)
    assert len(_otel_logging_handlers()) == 1


def test_bootstrap_export_false_then_export_true_raises_without_adding_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_noop_otlp_exporters(monkeypatch)

    _bootstrap(export=False)

    with pytest.raises(RuntimeError, match="already bootstrapped"):
        _bootstrap(export=True)

    assert _otel_logging_handlers() == []


def test_bootstrap_rejects_changed_settings_after_first_success() -> None:
    _bootstrap(export=False)

    with pytest.raises(RuntimeError, match="already bootstrapped"):
        _bootstrap(export=False, service_name="unit-service-2")


def test_bootstrap_rejects_external_preconfigured_tracer_provider() -> None:
    external_provider = TracerProvider()
    trace.set_tracer_provider(external_provider)

    with pytest.raises(RuntimeError, match="OpenTelemetry tracer provider"):
        _bootstrap(export=False)

    assert instrumentation._BOOTSTRAPPED is False
    assert trace.get_tracer_provider() is external_provider


def test_bootstrap_rejects_external_preconfigured_logger_provider() -> None:
    external_provider = LoggerProvider()
    set_logger_provider(external_provider)

    with pytest.raises(RuntimeError, match="OpenTelemetry logger provider"):
        _bootstrap(export=False)

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
        _bootstrap(export=True)

    assert instrumentation._BOOTSTRAPPED is False
    assert root_logger.getEffectiveLevel() == logging.WARNING

    monkeypatch.setattr(
        instrumentation,
        "_attach_logging_handler",
        original_attach_logging_handler,
    )

    settings = _bootstrap(export=True)

    assert settings.service_name == "unit-service"
    assert len(_otel_logging_handlers()) == 1


def test_bootstrap_success_log_handler_failure_does_not_break_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_noop_otlp_exporters(monkeypatch)
    root_logger = logging.getLogger()
    raising_handler = _RaisingHandler()
    root_logger.addHandler(raising_handler)

    try:
        settings = _bootstrap(export=True)

        assert settings.service_name == "unit-service"
        assert instrumentation._BOOTSTRAPPED is True
        assert len(_otel_logging_handlers()) == 1
        assert _bootstrap(export=True) is settings
    finally:
        root_logger.removeHandler(raising_handler)
        raising_handler.close()


def test_bootstrap_rollback_keeps_external_providers_after_install_race(monkeypatch: pytest.MonkeyPatch) -> None:
    external_tracer_provider = TracerProvider()
    external_logger_provider = LoggerProvider()

    def fail_after_external_provider_wins(*_: object) -> None:
        import opentelemetry._logs._internal as logs_internal
        import opentelemetry.trace as trace_api

        trace_api._TRACER_PROVIDER = external_tracer_provider
        trace_api._TRACER_PROVIDER_SET_ONCE._done = True
        logs_internal._LOGGER_PROVIDER = external_logger_provider
        logs_internal._LOGGER_PROVIDER_SET_ONCE._done = True
        raise RuntimeError("provider race")

    monkeypatch.setattr(instrumentation, "_ensure_active_otel_providers", fail_after_external_provider_wins)

    with pytest.raises(RuntimeError, match="provider race"):
        _bootstrap(export=False)

    assert instrumentation._BOOTSTRAPPED is False
    assert trace.get_tracer_provider() is external_tracer_provider
    assert get_logger_provider() is external_logger_provider


def test_bootstrap_rolls_back_tracer_provider_when_logger_provider_setter_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_set_logger_provider(_: LoggerProvider) -> None:
        raise RuntimeError("logger provider boom")

    with monkeypatch.context() as patch:
        patch.setattr(instrumentation, "set_logger_provider", fail_set_logger_provider)
        with pytest.raises(RuntimeError, match="logger provider boom"):
            _bootstrap(export=False)

    assert instrumentation._BOOTSTRAPPED is False
    assert instrumentation._configured_tracer_provider() is None
    assert _bootstrap(export=False).service_name == "unit-service"


def test_bootstrap_rollback_clears_owned_globals_when_shutdown_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_after_provider_install(*_: object) -> None:
        raise RuntimeError("post install boom")

    def fail_shutdown(_: object | None) -> None:
        raise RuntimeError("shutdown boom")

    with monkeypatch.context() as patch:
        patch.setattr(instrumentation, "_ensure_active_otel_providers", fail_after_provider_install)
        patch.setattr(instrumentation, "_shutdown_provider", fail_shutdown)
        with pytest.raises(RuntimeError, match="post install boom"):
            _bootstrap(export=False)

    assert instrumentation._configured_tracer_provider() is None
    assert instrumentation._configured_logger_provider() is None
    assert _bootstrap(export=False).service_name == "unit-service"


def test_bootstrap_export_true_enables_info_level_root_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_noop_otlp_exporters(monkeypatch)
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.WARNING)

    try:
        _bootstrap(export=True)

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
        _bootstrap(export=True)

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
    _bootstrap(export=False)
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


def _bootstrap(*, export: bool, **overrides: str) -> OpsBoardSettings:
    return bootstrap_observability(export=export, **(BOOTSTRAP_OVERRIDES | overrides))


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


class _RaisingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise RuntimeError("handler boom")

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
import pytest

from ops_board_observe import observe
import ops_board_observe.instrumentation as instrumentation
from ops_board_observe.instrumentation import _reset_for_tests

from conftest import (
    bootstrap_for_test,
    install_noop_otlp_exporters,
    install_slow_noop_otlp_exporters,
    otel_batch_processor_threads,
    otel_logging_handlers,
    wait_for_no_otel_batch_processor_threads,
)

PROVIDER_ENV_CASES = [
    ("OTEL_PYTHON_TRACER_PROVIDER", "tracer provider"),
    ("OTEL_PYTHON_LOGGER_PROVIDER", "logger provider"),
]


def test_bootstrap_returns_settings_with_export_disabled() -> None:
    settings = bootstrap_for_test(export=False)

    assert settings.service_name == "unit-service"
    assert settings.service_namespace == "unit-namespace"
    assert settings.owner == "unit-owner"
    assert settings.otlp_endpoint == "http://hp-15:4318"


def test_bootstrap_export_false_does_not_attach_otel_logging_handler_or_change_root_level() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    bootstrap_for_test(export=False)

    assert otel_logging_handlers() == []
    assert root_logger.getEffectiveLevel() == logging.WARNING


def test_reset_shuts_down_export_enabled_batch_processor_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    install_noop_otlp_exporters(monkeypatch)

    bootstrap_for_test(export=True)

    assert otel_batch_processor_threads()

    _reset_for_tests()

    assert wait_for_no_otel_batch_processor_threads()


def test_bootstrap_export_true_attaches_one_otel_logging_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    install_noop_otlp_exporters(monkeypatch)

    bootstrap_for_test(export=True)
    handlers = otel_logging_handlers()
    assert len(handlers) == 1
    first_handler = handlers[0]

    bootstrap_for_test(export=True)
    assert otel_logging_handlers() == [first_handler]

    _reset_for_tests()
    assert otel_logging_handlers() == []

    bootstrap_for_test(export=True, service_name="unit-service-3")
    handlers = otel_logging_handlers()
    assert len(handlers) == 1
    assert handlers[0] is not first_handler


def test_concurrent_identical_bootstrap_calls_share_one_active_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_slow_noop_otlp_exporters(monkeypatch)

    def call_bootstrap() -> object:
        return bootstrap_for_test(export=True)

    with ThreadPoolExecutor(max_workers=8) as executor:
        settings = list(executor.map(lambda _: call_bootstrap(), range(8)))

    assert all(setting is settings[0] for setting in settings)
    assert len(otel_logging_handlers()) == 1


def test_bootstrap_export_false_then_export_true_raises_without_adding_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_noop_otlp_exporters(monkeypatch)

    bootstrap_for_test(export=False)

    with pytest.raises(RuntimeError, match="already bootstrapped"):
        bootstrap_for_test(export=True)

    assert otel_logging_handlers() == []


def test_bootstrap_rejects_changed_settings_after_first_success() -> None:
    bootstrap_for_test(export=False)

    with pytest.raises(RuntimeError, match="already bootstrapped"):
        bootstrap_for_test(export=False, service_name="unit-service-2")


@pytest.mark.parametrize(
    ("provider", "setter", "getter", "message"),
    [
        (TracerProvider, trace.set_tracer_provider, trace.get_tracer_provider, "OpenTelemetry tracer provider"),
        (LoggerProvider, set_logger_provider, get_logger_provider, "OpenTelemetry logger provider"),
    ],
)
def test_bootstrap_rejects_external_preconfigured_provider(provider, setter, getter, message: str) -> None:
    external_provider = provider()
    setter(external_provider)

    with pytest.raises(RuntimeError, match=message):
        bootstrap_for_test(export=False)

    assert instrumentation._BOOTSTRAPPED is False
    assert getter() is external_provider


@pytest.mark.parametrize(("env_var", "message"), PROVIDER_ENV_CASES)
def test_bootstrap_rejects_env_configured_provider_intent(
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    message: str,
) -> None:
    monkeypatch.setenv(env_var, "configured-by-host")

    with pytest.raises(RuntimeError, match=message):
        bootstrap_for_test(export=False)

    assert instrumentation._configured_tracer_provider() is None
    assert instrumentation._configured_logger_provider() is None

    monkeypatch.delenv(env_var)
    assert bootstrap_for_test(export=False).service_name == "unit-service"


def test_bootstrap_rolls_back_provider_globals_after_logging_handler_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_noop_otlp_exporters(monkeypatch)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    original_attach_logging_handler = instrumentation._attach_logging_handler

    def fail_attach_logging_handler(logger_provider: LoggerProvider) -> None:
        raise RuntimeError("attach boom")

    monkeypatch.setattr(instrumentation, "_attach_logging_handler", fail_attach_logging_handler)

    with pytest.raises(RuntimeError, match="attach boom"):
        bootstrap_for_test(export=True)

    assert instrumentation._BOOTSTRAPPED is False
    assert root_logger.getEffectiveLevel() == logging.WARNING

    monkeypatch.setattr(instrumentation, "_attach_logging_handler", original_attach_logging_handler)
    settings = bootstrap_for_test(export=True)

    assert settings.service_name == "unit-service"
    assert len(otel_logging_handlers()) == 1


def test_bootstrap_success_log_handler_failure_does_not_break_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    install_noop_otlp_exporters(monkeypatch)
    root_logger = logging.getLogger()
    raising_handler = _RaisingHandler()
    root_logger.addHandler(raising_handler)

    try:
        settings = bootstrap_for_test(export=True)

        assert settings.service_name == "unit-service"
        assert instrumentation._BOOTSTRAPPED is True
        assert len(otel_logging_handlers()) == 1
        assert bootstrap_for_test(export=True) is settings
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
        bootstrap_for_test(export=False)

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
            bootstrap_for_test(export=False)

    assert instrumentation._BOOTSTRAPPED is False
    assert instrumentation._configured_tracer_provider() is None
    assert bootstrap_for_test(export=False).service_name == "unit-service"


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
            bootstrap_for_test(export=False)

    assert instrumentation._configured_tracer_provider() is None
    assert instrumentation._configured_logger_provider() is None
    assert bootstrap_for_test(export=False).service_name == "unit-service"


def test_clear_owned_otel_globals_holds_once_locks_before_identity_check() -> None:
    import opentelemetry._logs._internal as logs_internal
    import opentelemetry.trace as trace_api

    attempted_tracer_provider, external_tracer_provider = TracerProvider(), TracerProvider()
    attempted_logger_provider, external_logger_provider = LoggerProvider(), LoggerProvider()
    original_tracer_lock = trace_api._TRACER_PROVIDER_SET_ONCE._lock
    original_logger_lock = logs_internal._LOGGER_PROVIDER_SET_ONCE._lock
    trace_api._TRACER_PROVIDER = attempted_tracer_provider
    logs_internal._LOGGER_PROVIDER = attempted_logger_provider

    try:
        trace_api._TRACER_PROVIDER_SET_ONCE._lock = _ReplacingLock(
            lambda: setattr(trace_api, "_TRACER_PROVIDER", external_tracer_provider)
        )
        logs_internal._LOGGER_PROVIDER_SET_ONCE._lock = _ReplacingLock(
            lambda: setattr(logs_internal, "_LOGGER_PROVIDER", external_logger_provider)
        )
        instrumentation._clear_otel_globals_if_owned(attempted_tracer_provider, attempted_logger_provider)
    finally:
        trace_api._TRACER_PROVIDER_SET_ONCE._lock = original_tracer_lock
        logs_internal._LOGGER_PROVIDER_SET_ONCE._lock = original_logger_lock

    assert trace.get_tracer_provider() is external_tracer_provider
    assert get_logger_provider() is external_logger_provider


def test_reset_for_tests_clears_state_even_when_provider_shutdown_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    bootstrap_for_test(export=False)

    def fail_shutdown(_: object | None) -> None:
        raise RuntimeError("shutdown boom")

    with monkeypatch.context() as patch:
        patch.setattr(instrumentation, "_shutdown_provider", fail_shutdown)
        _reset_for_tests()

    assert instrumentation._BOOTSTRAPPED is False
    assert instrumentation._SETTINGS is None
    assert instrumentation._configured_tracer_provider() is None
    assert instrumentation._configured_logger_provider() is None
    assert bootstrap_for_test(export=False).service_name == "unit-service"


def test_bootstrap_export_true_enables_info_level_root_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    install_noop_otlp_exporters(monkeypatch)
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.WARNING)

    try:
        bootstrap_for_test(export=True)

        assert root_logger.getEffectiveLevel() <= logging.INFO
        assert logging.getLogger("ops_board_observe").isEnabledFor(logging.INFO)
    finally:
        root_logger.setLevel(original_level)


def test_bootstrap_export_true_adds_only_otel_handler_when_root_has_no_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_noop_otlp_exporters(monkeypatch)
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    for handler in original_handlers:
        root_logger.removeHandler(handler)

    try:
        bootstrap_for_test(export=True)

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
    bootstrap_for_test(export=False)
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


def _only_span(exporter: InMemorySpanExporter):
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    return spans[0]


class _RaisingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise RuntimeError("handler boom")


class _ReplacingLock:
    def __init__(self, replace: Callable[[], None]) -> None:
        self._replace = replace

    def __enter__(self) -> None:
        self._replace()

    def __exit__(self, *args: object) -> None:
        return None

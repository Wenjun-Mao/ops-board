from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import trace
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
import pytest

from ops_board_observe import observe
from ops_board_observe.instrumentation import _reset_for_tests

from conftest import (
    bootstrap_for_test,
    install_noop_otlp_exporters,
    install_slow_noop_otlp_exporters,
    otel_batch_processor_threads,
    otel_logging_handlers,
    wait_for_no_otel_batch_processor_threads,
)


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

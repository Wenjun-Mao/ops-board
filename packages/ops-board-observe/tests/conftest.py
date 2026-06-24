from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator

from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.sdk._logs.export import LogExportResult
from opentelemetry.sdk.trace.export import SpanExportResult
import pytest

from ops_board_observe import OpsBoardSettings, bootstrap_observability
import ops_board_observe.instrumentation as instrumentation
from ops_board_observe.instrumentation import _reset_for_tests

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
    remove_otel_logging_handlers()
    yield
    _reset_for_tests()
    remove_otel_logging_handlers()
    root_logger.setLevel(original_root_level)


def bootstrap_for_test(*, export: bool, **overrides: str) -> OpsBoardSettings:
    return bootstrap_observability(export=export, **(BOOTSTRAP_OVERRIDES | overrides))


def otel_logging_handlers() -> list[LoggingHandler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, LoggingHandler)
    ]


def remove_otel_logging_handlers() -> None:
    root_logger = logging.getLogger()
    for handler in otel_logging_handlers():
        root_logger.removeHandler(handler)


def otel_batch_processor_threads() -> list[threading.Thread]:
    return [
        thread
        for thread in threading.enumerate()
        if thread.name in {"OtelBatchSpanRecordProcessor", "OtelBatchLogRecordProcessor"}
    ]


def wait_for_no_otel_batch_processor_threads(timeout_seconds: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not otel_batch_processor_threads():
            return True
        time.sleep(0.01)
    return not otel_batch_processor_threads()


def install_noop_otlp_exporters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(instrumentation, "OTLPSpanExporter", _NoopSpanExporter)
    monkeypatch.setattr(instrumentation, "OTLPLogExporter", _NoopLogExporter)


def install_slow_noop_otlp_exporters(monkeypatch: pytest.MonkeyPatch) -> None:
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

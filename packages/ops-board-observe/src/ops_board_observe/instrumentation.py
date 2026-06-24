from __future__ import annotations

import functools
import inspect
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

from .settings import OpsBoardSettings, load_settings

P = ParamSpec("P")
R = TypeVar("R")

_BOOTSTRAPPED = False
_SETTINGS: OpsBoardSettings | None = None

_LOGGER = logging.getLogger("ops_board_observe")
_TRACER_NAME = "ops_board_observe"


def bootstrap_observability(
    config_path: str | Path | None = None,
    *,
    export: bool = True,
    **overrides: Any,
) -> OpsBoardSettings:
    settings = load_settings(config_path=config_path, **overrides)

    global _BOOTSTRAPPED, _SETTINGS
    if _BOOTSTRAPPED:
        _SETTINGS = settings
        return settings

    resource = Resource.create(_resource_attributes(settings))
    tracer_provider = TracerProvider(resource=resource)

    logger_provider = LoggerProvider(resource=resource)
    if export:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=_otlp_signal_endpoint(settings.otlp_endpoint, "traces"))
            )
        )
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                OTLPLogExporter(endpoint=_otlp_signal_endpoint(settings.otlp_endpoint, "logs"))
            )
        )

    trace.set_tracer_provider(tracer_provider)
    set_logger_provider(logger_provider)

    logging.basicConfig(level=logging.INFO)

    _BOOTSTRAPPED = True
    _SETTINGS = settings
    _LOGGER.info(
        "ops_board_observability_bootstrapped",
        extra={
            "export": export,
            "otlp_endpoint": settings.otlp_endpoint,
            "service_name": settings.service_name,
            "service_namespace": settings.service_namespace,
            "environment": settings.environment,
            "owner": settings.owner,
        },
    )
    return settings


def observe(
    span_name: str | None = None,
    *,
    attributes: Mapping[str, str | int | float | bool] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        resolved_span_name = span_name or f"{func.__module__}.{func.__qualname__}"
        span_attributes = dict(attributes or {})

        if inspect.iscoroutinefunction(func):
            async_func = cast(Callable[P, Awaitable[Any]], func)

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                start_time = time.perf_counter()
                tracer = trace.get_tracer(_TRACER_NAME)
                with tracer.start_as_current_span(resolved_span_name) as span:
                    _set_common_span_attributes(span, func, span_attributes)
                    try:
                        return await async_func(*args, **kwargs)
                    except Exception as exc:
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        raise
                    finally:
                        span.set_attribute("ops_board.duration_ms", _elapsed_ms(start_time))

            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start_time = time.perf_counter()
            tracer = trace.get_tracer(_TRACER_NAME)
            with tracer.start_as_current_span(resolved_span_name) as span:
                _set_common_span_attributes(span, func, span_attributes)
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise
                finally:
                    span.set_attribute("ops_board.duration_ms", _elapsed_ms(start_time))

        return sync_wrapper

    return decorator


def _otlp_signal_endpoint(base_endpoint: str, signal: str) -> str:
    endpoint = base_endpoint.rstrip("/")
    suffix = f"/v1/{signal}"
    if endpoint.endswith(suffix):
        return endpoint
    return f"{endpoint}{suffix}"


def _reset_for_tests() -> None:
    global _BOOTSTRAPPED, _SETTINGS
    _BOOTSTRAPPED = False
    _SETTINGS = None
    _reset_opentelemetry_globals_for_tests()


def _resource_attributes(settings: OpsBoardSettings) -> dict[str, str]:
    return {
        "service.name": settings.service_name,
        "service.namespace": settings.service_namespace,
        "service.version": settings.version,
        "deployment.environment": settings.environment,
        "ops_board.owner": settings.owner,
        "host.name": settings.runtime_host,
        **_optional_resource_attributes(
            {
                "ops_board.tailscale_host": settings.tailscale_host,
                "ops_board.runtime_provider": settings.runtime_provider,
                "ops_board.runtime_country": settings.runtime_country,
            }
        ),
    }


def _optional_resource_attributes(values: Mapping[str, str | None]) -> dict[str, str]:
    return {key: value for key, value in values.items() if value is not None}


def _set_common_span_attributes(
    span: trace.Span,
    func: Callable[..., Any],
    attributes: Mapping[str, str | int | float | bool],
) -> None:
    span.set_attribute("code.function", func.__qualname__)
    span.set_attribute("code.namespace", func.__module__)
    for key, value in attributes.items():
        span.set_attribute(key, value)


def _elapsed_ms(start_time: float) -> float:
    return (time.perf_counter() - start_time) * 1000


def _reset_opentelemetry_globals_for_tests() -> None:
    # OpenTelemetry intentionally makes providers set-once in production; tests need
    # isolated bootstrap cycles without leaking global providers across cases.
    import opentelemetry._logs._internal as logs_internal
    import opentelemetry.trace as trace_api

    trace_api._TRACER_PROVIDER = None
    trace_api._TRACER_PROVIDER_SET_ONCE._done = False
    logs_internal._LOGGER_PROVIDER = None
    logs_internal._LOGGER_PROVIDER_SET_ONCE._done = False

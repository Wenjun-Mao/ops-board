from __future__ import annotations

import functools
import inspect
import logging
import os
import threading
import time
import warnings
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

from opentelemetry import trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.environment_variables import (
    OTEL_PYTHON_TRACER_PROVIDER,
    _OTEL_PYTHON_LOGGER_PROVIDER,
)
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
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
_EXPORT_ENABLED: bool | None = None
_LOGGING_HANDLER: LoggingHandler | None = None
_TRACER_PROVIDER: TracerProvider | None = None
_LOGGER_PROVIDER: LoggerProvider | None = None
_BOOTSTRAP_LOCK = threading.RLock()

_LOGGER = logging.getLogger("ops_board_observe")
_LOGGING_HANDLER_MARKER = "_ops_board_observe_logging_handler"
_TRACER_NAME = "ops_board_observe"


def bootstrap_observability(
    config_path: str | Path | None = None,
    *,
    export: bool = True,
    **overrides: Any,
) -> OpsBoardSettings:
    settings = load_settings(config_path=config_path, **overrides)

    with _BOOTSTRAP_LOCK:
        return _bootstrap_observability_locked(settings, export)


def _bootstrap_observability_locked(settings: OpsBoardSettings, export: bool) -> OpsBoardSettings:
    global _BOOTSTRAPPED, _EXPORT_ENABLED, _LOGGER_PROVIDER, _SETTINGS, _TRACER_PROVIDER
    if _BOOTSTRAPPED:
        _validate_rebootstrap(settings, export)
        if _SETTINGS is None:
            raise RuntimeError("Ops Board observability bootstrap state is inconsistent")
        return _SETTINGS

    _ensure_no_existing_otel_provider_conflicts()

    resource = Resource.create(_resource_attributes(settings))
    tracer_provider = TracerProvider(resource=resource)
    logger_provider = LoggerProvider(resource=resource)

    try:
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
        _ensure_active_otel_providers(tracer_provider, logger_provider)

        if export:
            _attach_logging_handler(logger_provider)
            _configure_stdlib_logging()
    except Exception:
        _rollback_failed_bootstrap(
            tracer_provider=tracer_provider,
            logger_provider=logger_provider,
        )
        raise

    _BOOTSTRAPPED = True
    _SETTINGS = settings
    _EXPORT_ENABLED = export
    _TRACER_PROVIDER = tracer_provider
    _LOGGER_PROVIDER = logger_provider
    _log_bootstrap_success(settings=settings, export=export)
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
                with tracer.start_as_current_span(
                    resolved_span_name,
                    record_exception=False,
                    set_status_on_exception=False,
                ) as span:
                    _set_common_span_attributes(span, func, span_attributes)
                    try:
                        result = await async_func(*args, **kwargs)
                    except Exception as exc:
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        raise
                    else:
                        span.set_status(Status(StatusCode.OK))
                        return result
                    finally:
                        span.set_attribute("ops_board.duration_ms", _elapsed_ms(start_time))

            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start_time = time.perf_counter()
            tracer = trace.get_tracer(_TRACER_NAME)
            with tracer.start_as_current_span(
                resolved_span_name,
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                _set_common_span_attributes(span, func, span_attributes)
                try:
                    result = func(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise
                else:
                    span.set_status(Status(StatusCode.OK))
                    return result
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
    global _BOOTSTRAPPED, _EXPORT_ENABLED, _LOGGER_PROVIDER, _LOGGING_HANDLER, _SETTINGS, _TRACER_PROVIDER
    with _BOOTSTRAP_LOCK:
        logger_provider = _LOGGER_PROVIDER
        tracer_provider = _TRACER_PROVIDER
        _run_cleanup_steps(
            _detach_logging_handler,
            lambda: _clear_otel_globals_if_owned(tracer_provider, logger_provider),
            lambda: _shutdown_provider(logger_provider),
            lambda: _shutdown_provider(tracer_provider),
        )
        _BOOTSTRAPPED = False
        _SETTINGS = None
        _EXPORT_ENABLED = None
        _LOGGING_HANDLER = None
        _LOGGER_PROVIDER = None
        _TRACER_PROVIDER = None
        _force_clear_otel_globals_for_tests()


def _resource_attributes(settings: OpsBoardSettings) -> dict[str, str]:
    return {
        "service.name": settings.service_name,
        "service.namespace": settings.service_namespace,
        "service.version": settings.version,
        "deployment.environment": settings.environment,
        "service.owner": settings.owner,
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


def _validate_rebootstrap(settings: OpsBoardSettings, export: bool) -> None:
    if (
        _SETTINGS is not None
        and settings.model_dump() == _SETTINGS.model_dump()
        and export == _EXPORT_ENABLED
    ):
        return
    raise RuntimeError(
        "Ops Board observability is already bootstrapped and cannot be reconfigured "
        "in-process. Restart the process or call bootstrap_observability with the "
        "same effective settings and export flag."
    )


def _ensure_no_existing_otel_provider_conflicts() -> None:
    _ensure_no_otel_provider_env_conflicts()

    tracer_provider = _configured_tracer_provider()
    if tracer_provider is not None:
        raise RuntimeError(
            "OpenTelemetry tracer provider is already configured before Ops Board "
            "observability bootstrap. Configure Ops Board observability first, or "
            "avoid bootstrapping it in this process."
        )

    logger_provider = _configured_logger_provider()
    if logger_provider is not None:
        raise RuntimeError(
            "OpenTelemetry logger provider is already configured before Ops Board "
            "observability bootstrap. Configure Ops Board observability first, or "
            "avoid bootstrapping it in this process."
        )


def _ensure_no_otel_provider_env_conflicts() -> None:
    provider_env_vars = (
        (OTEL_PYTHON_TRACER_PROVIDER, "tracer provider"),
        (_OTEL_PYTHON_LOGGER_PROVIDER, "logger provider"),
    )
    for env_var, provider_name in provider_env_vars:
        if env_var in os.environ:
            raise RuntimeError(
                f"OpenTelemetry {provider_name} is configured by {env_var} before "
                "Ops Board observability bootstrap. Remove that environment variable "
                "or let the host application own observability bootstrap."
            )


def _ensure_active_otel_providers(
    tracer_provider: TracerProvider,
    logger_provider: LoggerProvider,
) -> None:
    if trace.get_tracer_provider() is not tracer_provider:
        raise RuntimeError(
            "Ops Board observability failed to install its OpenTelemetry tracer provider"
        )
    if get_logger_provider() is not logger_provider:
        raise RuntimeError(
            "Ops Board observability failed to install its OpenTelemetry logger provider"
        )


def _rollback_failed_bootstrap(
    *,
    tracer_provider: TracerProvider,
    logger_provider: LoggerProvider,
) -> None:
    _run_cleanup_steps(
        lambda: _clear_otel_globals_if_owned(tracer_provider, logger_provider),
        _detach_logging_handler,
        lambda: _shutdown_provider(logger_provider),
        lambda: _shutdown_provider(tracer_provider),
    )


def _run_cleanup_steps(*cleanup_steps: Callable[[], None]) -> None:
    for cleanup_step in cleanup_steps:
        try:
            cleanup_step()
        except Exception:
            # Preserve the original bootstrap failure; cleanup is best-effort.
            continue


def _shutdown_provider(provider: object | None) -> None:
    if provider is not None:
        cast(Any, provider).shutdown()


def _log_bootstrap_success(*, settings: OpsBoardSettings, export: bool) -> None:
    try:
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
    except Exception:
        # Host-owned logging handlers should not invalidate a completed bootstrap.
        return


def _configure_stdlib_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.getEffectiveLevel() > logging.INFO:
        root_logger.setLevel(logging.INFO)


def _attach_logging_handler(logger_provider: LoggerProvider) -> None:
    global _LOGGING_HANDLER
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, LoggingHandler) and getattr(handler, _LOGGING_HANDLER_MARKER, False):
            _LOGGING_HANDLER = handler
            return

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="`LoggingHandler` in `opentelemetry-sdk` is deprecated.*",
            category=DeprecationWarning,
        )
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    setattr(handler, _LOGGING_HANDLER_MARKER, True)
    root_logger.addHandler(handler)
    _LOGGING_HANDLER = handler


def _detach_logging_handler() -> None:
    global _LOGGING_HANDLER
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        if handler is _LOGGING_HANDLER or (
            isinstance(handler, LoggingHandler) and getattr(handler, _LOGGING_HANDLER_MARKER, False)
        ):
            root_logger.removeHandler(handler)
            handler.close()
    _LOGGING_HANDLER = None


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


def _configured_tracer_provider() -> object | None:
    # OpenTelemetry exposes provider installation as process-global set-once state.
    # Public getters return proxy providers when unset, so conflict detection needs
    # this narrow private-state read before calling set_tracer_provider().
    import opentelemetry.trace as trace_api

    return trace_api._TRACER_PROVIDER


def _configured_logger_provider() -> object | None:
    # Mirrors _configured_tracer_provider for the logs API's set-once global.
    import opentelemetry._logs._internal as logs_internal

    return logs_internal._LOGGER_PROVIDER


def _clear_otel_globals_if_owned(
    tracer_provider: object | None,
    logger_provider: object | None,
) -> None:
    # Production rollback may touch OTel's set-once private globals, but only when
    # they still point to the providers created by the failed bootstrap attempt.
    import opentelemetry._logs._internal as logs_internal
    import opentelemetry.trace as trace_api

    with trace_api._TRACER_PROVIDER_SET_ONCE._lock:
        if tracer_provider is not None and trace_api._TRACER_PROVIDER is tracer_provider:
            trace_api._TRACER_PROVIDER = None
            trace_api._TRACER_PROVIDER_SET_ONCE._done = False
    with logs_internal._LOGGER_PROVIDER_SET_ONCE._lock:
        if logger_provider is not None and logs_internal._LOGGER_PROVIDER is logger_provider:
            logs_internal._LOGGER_PROVIDER = None
            logs_internal._LOGGER_PROVIDER_SET_ONCE._done = False


def _force_clear_otel_globals_for_tests() -> None:
    # OpenTelemetry intentionally makes providers set-once in production; tests need
    # isolated bootstrap cycles without leaking global providers across cases.
    import opentelemetry._logs._internal as logs_internal
    import opentelemetry.trace as trace_api

    trace_api._TRACER_PROVIDER = None
    trace_api._TRACER_PROVIDER_SET_ONCE._done = False
    logs_internal._LOGGER_PROVIDER = None
    logs_internal._LOGGER_PROVIDER_SET_ONCE._done = False

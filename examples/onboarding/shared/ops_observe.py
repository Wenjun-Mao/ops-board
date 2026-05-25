from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import os
import socket
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

import yaml
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

P = ParamSpec("P")
R = TypeVar("R")

_BOOTSTRAPPED = False
_SETTINGS: OpsBoardSettings | None = None
_LOGGER = logging.getLogger("ops_board.onboarding")


class OpsBoardSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPS_BOARD_",
        extra="ignore",
    )

    service_name: str = "unknown-service"
    service_namespace: str = "default"
    environment: str = "local"
    owner: str = "unknown"
    version: str = "0.1.0"
    runtime_host: str = Field(default_factory=socket.gethostname)
    tailscale_host: str | None = None
    runtime_provider: str | None = None
    runtime_country: str | None = None
    otlp_endpoint: str = "http://localhost:4318"
    health_url: str | None = None
    secrets_dir: str = "/run/secrets"


def load_settings(config_path: str | Path | None = None, **overrides: Any) -> OpsBoardSettings:
    config_values = _read_config_values(config_path)
    env_values = _read_env_values()
    secrets_dir = overrides.get("secrets_dir") or env_values.get("secrets_dir") or config_values.get("secrets_dir")
    secret_values = _read_secret_values(Path(str(secrets_dir or "/run/secrets")))
    explicit_values = _without_none(overrides)

    values: dict[str, Any] = {}
    values.update(config_values)
    values.update(env_values)
    values.update(secret_values)
    values.update(explicit_values)
    return OpsBoardSettings.model_validate(values)


def bootstrap_observability(
    config_path: str | Path | None = None,
    *,
    export: bool = True,
    **overrides: Any,
) -> OpsBoardSettings:
    global _BOOTSTRAPPED, _SETTINGS

    settings = load_settings(config_path=config_path, **overrides)
    _SETTINGS = settings

    if _BOOTSTRAPPED:
        return settings

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.namespace": settings.service_namespace,
            "service.version": settings.version,
            "deployment.environment": settings.environment,
            "service.owner": settings.owner,
            "host.name": settings.runtime_host,
            "ops_board.tailscale_host": settings.tailscale_host or "",
            "ops_board.runtime_provider": settings.runtime_provider or "",
            "ops_board.runtime_country": settings.runtime_country or "",
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    if export:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=_otlp_signal_endpoint(settings.otlp_endpoint, "traces"))
            )
        )
    trace.set_tracer_provider(tracer_provider)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if export:
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                OTLPLogExporter(endpoint=_otlp_signal_endpoint(settings.otlp_endpoint, "logs"))
            )
        )
        set_logger_provider(logger_provider)
        logging.getLogger().addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))

    _BOOTSTRAPPED = True
    _LOGGER.info(
        "ops_board_observability_bootstrapped",
        extra={
            "service_name": settings.service_name,
            "service_namespace": settings.service_namespace,
            "environment": settings.environment,
            "runtime_host": settings.runtime_host,
        },
    )
    return settings


def observe(
    span_name: str | None = None,
    *,
    attributes: Mapping[str, str | int | float | bool] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        name = span_name or f"{function.__module__}.{function.__name__}"

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                return await _run_observed_async(function, name, attributes or {}, *args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(function)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return _run_observed_sync(function, name, attributes or {}, *args, **kwargs)

        return sync_wrapper

    return decorator


def _run_observed_sync(
    function: Callable[P, R],
    span_name: str,
    attributes: Mapping[str, str | int | float | bool],
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    tracer = trace.get_tracer("ops_board.onboarding")
    started_at = time.perf_counter()
    with tracer.start_as_current_span(span_name) as span:
        _set_common_span_attributes(span, function, attributes)
        try:
            result = function(*args, **kwargs)
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            _LOGGER.exception("observed_function_failed", extra={"span_name": span_name})
            raise
        span.set_attribute("ops_board.duration_ms", round((time.perf_counter() - started_at) * 1000, 3))
        span.set_status(Status(StatusCode.OK))
        return result


async def _run_observed_async(
    function: Callable[P, R],
    span_name: str,
    attributes: Mapping[str, str | int | float | bool],
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    tracer = trace.get_tracer("ops_board.onboarding")
    started_at = time.perf_counter()
    with tracer.start_as_current_span(span_name) as span:
        _set_common_span_attributes(span, function, attributes)
        try:
            result = function(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            _LOGGER.exception("observed_async_function_failed", extra={"span_name": span_name})
            raise
        span.set_attribute("ops_board.duration_ms", round((time.perf_counter() - started_at) * 1000, 3))
        span.set_status(Status(StatusCode.OK))
        return result


def _set_common_span_attributes(
    span: Span,
    function: Callable[..., Any],
    attributes: Mapping[str, str | int | float | bool],
) -> None:
    settings = _SETTINGS
    common = {
        "code.function": function.__name__,
        "code.namespace": function.__module__,
    }
    if settings is not None:
        common.update(
            {
                "service.name": settings.service_name,
                "service.namespace": settings.service_namespace,
                "deployment.environment": settings.environment,
                "service.owner": settings.owner,
                "host.name": settings.runtime_host,
            }
        )
    span.set_attributes(common)
    span.set_attributes(dict(attributes))


def _read_config_values(config_path: str | Path | None) -> dict[str, Any]:
    path = _resolve_config_path(config_path)
    if path is None or not path.exists():
        return {}

    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")

    service = _mapping(loaded.get("service"))
    runtime = _mapping(loaded.get("runtime"))
    ops_board = _mapping(loaded.get("ops_board"))

    return _without_none(
        {
            "service_name": service.get("name"),
            "service_namespace": service.get("namespace"),
            "environment": service.get("environment"),
            "owner": service.get("owner"),
            "version": service.get("version"),
            "runtime_host": runtime.get("host"),
            "tailscale_host": runtime.get("tailscale_host"),
            "runtime_provider": runtime.get("provider"),
            "runtime_country": runtime.get("country"),
            "otlp_endpoint": ops_board.get("otlp_endpoint"),
            "health_url": ops_board.get("health_url"),
        }
    )


def _read_env_values() -> dict[str, Any]:
    names = {
        "service_name": "OPS_BOARD_SERVICE_NAME",
        "service_namespace": "OPS_BOARD_SERVICE_NAMESPACE",
        "environment": "OPS_BOARD_ENVIRONMENT",
        "owner": "OPS_BOARD_OWNER",
        "version": "OPS_BOARD_VERSION",
        "runtime_host": "OPS_BOARD_RUNTIME_HOST",
        "tailscale_host": "OPS_BOARD_TAILSCALE_HOST",
        "runtime_provider": "OPS_BOARD_RUNTIME_PROVIDER",
        "runtime_country": "OPS_BOARD_RUNTIME_COUNTRY",
        "otlp_endpoint": "OPS_BOARD_OTLP_ENDPOINT",
        "health_url": "OPS_BOARD_HEALTH_URL",
        "secrets_dir": "OPS_BOARD_SECRETS_DIR",
    }
    return _without_none({field: os.environ.get(env_name) for field, env_name in names.items()})


def _read_secret_values(secrets_dir: Path) -> dict[str, Any]:
    if not secrets_dir.exists():
        return {}

    values: dict[str, Any] = {}
    for field in OpsBoardSettings.model_fields:
        secret_path = secrets_dir / field
        if secret_path.is_file():
            values[field] = secret_path.read_text(encoding="utf-8").strip()
    return _without_none(values)


def _resolve_config_path(config_path: str | Path | None) -> Path | None:
    explicit = config_path or os.environ.get("OPS_BOARD_CONFIG_FILE")
    if explicit:
        return Path(explicit)

    default = Path("ops-board.yaml")
    if default.exists():
        return default
    return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _without_none(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _otlp_signal_endpoint(base_endpoint: str, signal: str) -> str:
    endpoint = base_endpoint.rstrip("/")
    if endpoint.endswith(f"/v1/{signal}"):
        return endpoint
    return f"{endpoint}/v1/{signal}"

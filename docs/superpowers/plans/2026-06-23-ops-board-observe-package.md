# Ops Board Observe Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small internal Python package that colleagues can install, import, validate, and remove cleanly when onboarding Python projects to Ops Board.

**Architecture:** Move the current playground-only observability helper into `packages/ops-board-observe` as the canonical integration package. The onboarding playground will consume that package through local path dependencies, so examples use the same import path as real projects. Reader-facing docs will present `http://hp-15:4318` as the default OTLP endpoint for colleague projects running elsewhere on the tailnet.

**Tech Stack:** Python 3.12, `uv`, `pytest`, `pydantic-settings`, PyYAML, OpenTelemetry OTLP HTTP exporters, `tenacity`, Docker Compose.

---

## Important Worktree Note

At plan creation time, the worktree contains unstaged onboarding-doc edits from a superseded "copy/adapt helper" direction:

```text
docs/monitoring/ops-board-user-manual.md
docs/onboarding/codex-guide.md
docs/onboarding/human-guide.md
docs/onboarding/onboarding-contract.md
examples/onboarding/README.md
```

Do not commit those edits as-is. Task 5 replaces those docs with the package-first onboarding flow.

## File Structure

Create package files:

```text
packages/ops-board-observe/
  pyproject.toml
  src/ops_board_observe/
    __init__.py
    instrumentation.py
    settings.py
    py.typed
  tests/
    test_instrumentation.py
    test_settings.py
```

Modify playground files:

```text
examples/onboarding/pyproject.toml
examples/onboarding/uv.lock
examples/onboarding/compose.yaml
examples/onboarding/dummy-api/Dockerfile
examples/onboarding/dummy-api/app.py
examples/onboarding/dummy-api/pyproject.toml
examples/onboarding/dummy-api/uv.lock
examples/onboarding/dummy-job/Dockerfile
examples/onboarding/dummy-job/job.py
examples/onboarding/dummy-job/pyproject.toml
examples/onboarding/dummy-job/uv.lock
examples/onboarding/tests/test_ops_observe.py
```

Remove after playground imports from the package:

```text
examples/onboarding/shared/__init__.py
examples/onboarding/shared/ops_observe.py
```

Modify docs:

```text
docs/onboarding/human-guide.md
docs/onboarding/codex-guide.md
docs/onboarding/onboarding-contract.md
examples/onboarding/README.md
docs/monitoring/ops-board-user-manual.md
```

## Task 1: Package Settings Contract

**Files:**
- Create: `packages/ops-board-observe/pyproject.toml`
- Create: `packages/ops-board-observe/src/ops_board_observe/__init__.py`
- Create: `packages/ops-board-observe/src/ops_board_observe/settings.py`
- Create: `packages/ops-board-observe/src/ops_board_observe/py.typed`
- Create: `packages/ops-board-observe/tests/test_settings.py`

- [ ] **Step 1: Create the package skeleton**

Create `packages/ops-board-observe/pyproject.toml`:

```toml
[project]
name = "ops-board-observe"
version = "0.1.0"
description = "Python observability helper for Ops Board onboarding"
requires-python = ">=3.12"
dependencies = [
  "opentelemetry-api>=1.39.0",
  "opentelemetry-exporter-otlp-proto-http>=1.39.0",
  "opentelemetry-sdk>=1.39.0",
  "pydantic-settings>=2.12.0",
  "pyyaml>=6.0.2",
  "tenacity>=9.1.0",
]

[dependency-groups]
dev = [
  "pytest>=9.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create empty package files:

```bash
mkdir -p packages/ops-board-observe/src/ops_board_observe packages/ops-board-observe/tests
touch packages/ops-board-observe/src/ops_board_observe/__init__.py
touch packages/ops-board-observe/src/ops_board_observe/settings.py
touch packages/ops-board-observe/src/ops_board_observe/py.typed
```

- [ ] **Step 2: Write failing settings tests**

Create `packages/ops-board-observe/tests/test_settings.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from ops_board_observe import OpsBoardSettings, load_settings


def test_load_settings_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "ops-board.yaml"
    config_file.write_text(
        """
service:
  name: config-service
  namespace: config-namespace
  environment: config-env
  owner: config-owner
  version: 9.9.9
runtime:
  host: config-host
  tailscale_host: config-tailnet-host
  provider: local
  country: CA
ops_board:
  otlp_endpoint: http://config-collector:4318
  health_url: http://config-service:8000/health
""",
        encoding="utf-8",
    )

    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "service_name").write_text("secret-service", encoding="utf-8")

    monkeypatch.setenv("OPS_BOARD_SECRETS_DIR", str(secrets_dir))
    monkeypatch.setenv("OPS_BOARD_OWNER", "env-owner")
    monkeypatch.setenv("OPS_BOARD_ENVIRONMENT", "env")

    settings = load_settings(config_path=config_file, service_namespace="arg-namespace")

    assert settings.service_name == "secret-service"
    assert settings.service_namespace == "arg-namespace"
    assert settings.environment == "env"
    assert settings.owner == "env-owner"
    assert settings.version == "9.9.9"
    assert settings.runtime_host == "config-host"
    assert settings.tailscale_host == "config-tailnet-host"
    assert settings.runtime_provider == "local"
    assert settings.runtime_country == "CA"
    assert settings.otlp_endpoint == "http://config-collector:4318"
    assert settings.health_url == "http://config-service:8000/health"


def test_settings_defaults_are_safe_for_local_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in tuple(monkeypatch.context().__dict__.keys()):
        key

    settings = OpsBoardSettings()

    assert settings.service_name == "unknown-service"
    assert settings.service_namespace == "default"
    assert settings.environment == "local"
    assert settings.owner == "unknown"
    assert settings.otlp_endpoint == "http://localhost:4318"


def test_invalid_config_file_shape_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "ops-board.yaml"
    config_file.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Config file must contain a YAML mapping"):
        load_settings(config_path=config_file)
```

- [ ] **Step 3: Run settings tests to verify they fail**

Run:

```bash
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests/test_settings.py -q
```

Expected: FAIL because `OpsBoardSettings` and `load_settings` are not implemented or not exported.

- [ ] **Step 4: Implement settings module**

Replace `packages/ops-board-observe/src/ops_board_observe/settings.py` with:

```python
from __future__ import annotations

import os
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpsBoardSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPS_BOARD_", extra="ignore")

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
```

Replace `packages/ops-board-observe/src/ops_board_observe/__init__.py` with:

```python
from .settings import OpsBoardSettings, load_settings

__all__ = [
    "OpsBoardSettings",
    "load_settings",
]
```

- [ ] **Step 5: Fix the default test environment**

The default test should not try to introspect monkeypatch internals. Replace `test_settings_defaults_are_safe_for_local_tests` with:

```python
def test_settings_defaults_are_safe_for_local_tests() -> None:
    settings = OpsBoardSettings()

    assert settings.service_name == "unknown-service"
    assert settings.service_namespace == "default"
    assert settings.environment == "local"
    assert settings.owner == "unknown"
    assert settings.otlp_endpoint == "http://localhost:4318"
```

- [ ] **Step 6: Run settings tests to verify they pass**

Run:

```bash
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests/test_settings.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit settings package**

```bash
git add packages/ops-board-observe
git commit -m "feat: add ops board observe settings package"
```

## Task 2: Package Instrumentation And Observe Decorator

**Files:**
- Create: `packages/ops-board-observe/src/ops_board_observe/instrumentation.py`
- Modify: `packages/ops-board-observe/src/ops_board_observe/__init__.py`
- Create: `packages/ops-board-observe/tests/test_instrumentation.py`

- [ ] **Step 1: Write failing instrumentation tests**

Create `packages/ops-board-observe/tests/test_instrumentation.py`:

```python
from __future__ import annotations

import pytest

from ops_board_observe import bootstrap_observability, observe
from ops_board_observe.instrumentation import _otlp_signal_endpoint, _reset_for_tests


def test_otlp_signal_endpoint_adds_signal_suffix() -> None:
    assert _otlp_signal_endpoint("http://hp-15:4318", "traces") == "http://hp-15:4318/v1/traces"
    assert _otlp_signal_endpoint("http://hp-15:4318/", "logs") == "http://hp-15:4318/v1/logs"
    assert _otlp_signal_endpoint("http://hp-15:4318/v1/traces", "traces") == "http://hp-15:4318/v1/traces"


def test_bootstrap_returns_settings_with_export_disabled() -> None:
    _reset_for_tests()

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


def test_observe_returns_wrapped_function_result() -> None:
    @observe("unit.success")
    def add(left: int, right: int) -> int:
        return left + right

    assert add(2, 3) == 5


def test_observe_records_and_reraises_exceptions() -> None:
    @observe("unit.failure")
    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        fail()


@pytest.mark.asyncio
async def test_observe_supports_async_functions() -> None:
    @observe("unit.async")
    async def async_add(left: int, right: int) -> int:
        return left + right

    assert await async_add(2, 4) == 6
```

- [ ] **Step 2: Run instrumentation tests to verify they fail**

Run:

```bash
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests/test_instrumentation.py -q
```

Expected: FAIL because instrumentation functions are not implemented or not exported.

- [ ] **Step 3: Add pytest async dependency**

Modify `packages/ops-board-observe/pyproject.toml` dev group:

```toml
[dependency-groups]
dev = [
  "pytest>=9.0.0",
  "pytest-asyncio>=1.3.0",
]
```

- [ ] **Step 4: Implement instrumentation module**

Create `packages/ops-board-observe/src/ops_board_observe/instrumentation.py`:

```python
from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

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

from .settings import OpsBoardSettings, load_settings

P = ParamSpec("P")
R = TypeVar("R")

_BOOTSTRAPPED = False
_SETTINGS: OpsBoardSettings | None = None
_LOGGER = logging.getLogger("ops_board_observe")


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
            BatchSpanProcessor(OTLPSpanExporter(endpoint=_otlp_signal_endpoint(settings.otlp_endpoint, "traces")))
        )
    trace.set_tracer_provider(tracer_provider)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if export:
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=_otlp_signal_endpoint(settings.otlp_endpoint, "logs")))
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
    tracer = trace.get_tracer("ops_board_observe")
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
    tracer = trace.get_tracer("ops_board_observe")
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


def _otlp_signal_endpoint(base_endpoint: str, signal: str) -> str:
    endpoint = base_endpoint.rstrip("/")
    if endpoint.endswith(f"/v1/{signal}"):
        return endpoint
    return f"{endpoint}/v1/{signal}"


def _reset_for_tests() -> None:
    global _BOOTSTRAPPED, _SETTINGS
    _BOOTSTRAPPED = False
    _SETTINGS = None
```

- [ ] **Step 5: Export instrumentation API**

Replace `packages/ops-board-observe/src/ops_board_observe/__init__.py` with:

```python
from .instrumentation import bootstrap_observability, observe
from .settings import OpsBoardSettings, load_settings

__all__ = [
    "OpsBoardSettings",
    "bootstrap_observability",
    "load_settings",
    "observe",
]
```

- [ ] **Step 6: Run package tests**

Run:

```bash
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests -q
```

Expected: PASS.

- [ ] **Step 7: Commit instrumentation package**

```bash
git add packages/ops-board-observe
git commit -m "feat: add ops board observe instrumentation"
```

## Task 3: Switch Playground To Package Dependency

**Files:**
- Modify: `examples/onboarding/pyproject.toml`
- Modify: `examples/onboarding/dummy-api/pyproject.toml`
- Modify: `examples/onboarding/dummy-job/pyproject.toml`
- Modify: `examples/onboarding/tests/test_ops_observe.py`
- Modify: `examples/onboarding/dummy-api/app.py`
- Modify: `examples/onboarding/dummy-job/job.py`
- Delete: `examples/onboarding/shared/__init__.py`
- Delete: `examples/onboarding/shared/ops_observe.py`
- Update: `examples/onboarding/uv.lock`
- Update: `examples/onboarding/dummy-api/uv.lock`
- Update: `examples/onboarding/dummy-job/uv.lock`

- [ ] **Step 1: Update playground root dependency**

In `examples/onboarding/pyproject.toml`, add `ops-board-observe` and remove direct dependencies now owned by the package:

```toml
[project]
name = "ops-board-onboarding-playground"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.128.0",
  "httpx>=0.28.0",
  "loguru>=0.7.3",
  "ops-board-observe",
  "pytest>=9.0.0",
  "tenacity>=9.1.0",
  "uvicorn[standard]>=0.38.0",
]

[tool.uv]
package = false

[tool.uv.sources]
ops-board-observe = { path = "../../packages/ops-board-observe", editable = true }

[tool.pytest.ini_options]
pythonpath = [".", "dummy-job", "dummy-api"]
testpaths = [
  "tests",
  "dummy-job/tests",
  "dummy-api/tests",
]
```

- [ ] **Step 2: Update dummy app dependencies**

Replace `examples/onboarding/dummy-api/pyproject.toml` with:

```toml
[project]
name = "ops-board-dummy-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.128.0",
  "httpx>=0.28.0",
  "loguru>=0.7.3",
  "ops-board-observe",
  "pytest>=9.0.0",
  "tenacity>=9.1.0",
  "uvicorn[standard]>=0.38.0",
]

[tool.uv]
package = false

[tool.uv.sources]
ops-board-observe = { path = "../../../packages/ops-board-observe", editable = true }

[tool.pytest.ini_options]
pythonpath = ["..", "."]
testpaths = ["tests"]
```

Replace `examples/onboarding/dummy-job/pyproject.toml` with:

```toml
[project]
name = "ops-board-dummy-job"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "loguru>=0.7.3",
  "ops-board-observe",
  "pytest>=9.0.0",
  "tenacity>=9.1.0",
]

[tool.uv]
package = false

[tool.uv.sources]
ops-board-observe = { path = "../../../packages/ops-board-observe", editable = true }

[tool.pytest.ini_options]
pythonpath = ["..", "."]
testpaths = ["tests"]
```

- [ ] **Step 3: Update imports**

In `examples/onboarding/tests/test_ops_observe.py`, replace:

```python
from shared.ops_observe import observe, load_settings
```

with:

```python
from ops_board_observe import load_settings, observe
```

In `examples/onboarding/dummy-api/app.py`, replace:

```python
from shared.ops_observe import bootstrap_observability, observe
```

with:

```python
from ops_board_observe import bootstrap_observability, observe
```

In `examples/onboarding/dummy-job/job.py`, replace:

```python
from shared.ops_observe import bootstrap_observability, observe
```

with:

```python
from ops_board_observe import bootstrap_observability, observe
```

- [ ] **Step 4: Remove local shared helper**

Delete:

```text
examples/onboarding/shared/__init__.py
examples/onboarding/shared/ops_observe.py
```

- [ ] **Step 5: Refresh locks**

Run:

```bash
uv lock --project packages/ops-board-observe
uv lock --project examples/onboarding
uv lock --project examples/onboarding/dummy-api
uv lock --project examples/onboarding/dummy-job
```

Expected: lock files update without dependency resolution errors. `packages/ops-board-observe/uv.lock` may be created.

- [ ] **Step 6: Run package and playground tests**

Run:

```bash
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests -q
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -q
```

Expected: both commands PASS.

- [ ] **Step 7: Commit playground package migration**

```bash
git add packages/ops-board-observe/uv.lock examples/onboarding examples/onboarding/dummy-api examples/onboarding/dummy-job
git add -u examples/onboarding/shared
git commit -m "feat: use observe package in onboarding playground"
```

## Task 4: Update Playground Docker Builds

**Files:**
- Modify: `examples/onboarding/compose.yaml`
- Modify: `examples/onboarding/dummy-api/Dockerfile`
- Modify: `examples/onboarding/dummy-job/Dockerfile`

- [ ] **Step 1: Change compose build contexts to repo root**

In `examples/onboarding/compose.yaml`, update both build blocks.

For `dummy-api`:

```yaml
    build:
      context: ../..
      dockerfile: examples/onboarding/dummy-api/Dockerfile
```

For `dummy-job`:

```yaml
    build:
      context: ../..
      dockerfile: examples/onboarding/dummy-job/Dockerfile
```

- [ ] **Step 2: Update dummy API Dockerfile**

Replace `examples/onboarding/dummy-api/Dockerfile` with:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /uvx /bin/

WORKDIR /repo/examples/onboarding/dummy-api

COPY packages/ops-board-observe /repo/packages/ops-board-observe
COPY examples/onboarding/dummy-api/pyproject.toml ./pyproject.toml
COPY examples/onboarding/dummy-api/uv.lock ./uv.lock
RUN --mount=type=cache,target=/root/.cache/uv uv sync --no-dev --no-install-project

COPY examples/onboarding/dummy-api/app.py ./app.py

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Update dummy job Dockerfile**

Replace `examples/onboarding/dummy-job/Dockerfile` with:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /uvx /bin/

WORKDIR /repo/examples/onboarding/dummy-job

COPY packages/ops-board-observe /repo/packages/ops-board-observe
COPY examples/onboarding/dummy-job/pyproject.toml ./pyproject.toml
COPY examples/onboarding/dummy-job/uv.lock ./uv.lock
RUN --mount=type=cache,target=/root/.cache/uv uv sync --no-dev --no-install-project

COPY examples/onboarding/dummy-job/job.py ./job.py

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "job.py"]
```

- [ ] **Step 4: Verify compose config and builds**

Run:

```bash
docker compose -f examples/onboarding/compose.yaml config --quiet
docker compose -f examples/onboarding/compose.yaml build dummy-api dummy-job
```

Expected: both commands exit 0.

- [ ] **Step 5: Commit Docker playground updates**

```bash
git add examples/onboarding/compose.yaml examples/onboarding/dummy-api/Dockerfile examples/onboarding/dummy-job/Dockerfile
git commit -m "build: package onboarding playground containers"
```

## Task 5: Rewrite Onboarding Docs Around Package Flow

**Files:**
- Modify: `docs/onboarding/human-guide.md`
- Modify: `docs/onboarding/codex-guide.md`
- Modify: `docs/onboarding/onboarding-contract.md`
- Modify: `examples/onboarding/README.md`
- Modify: `docs/monitoring/ops-board-user-manual.md`

- [ ] **Step 1: Update human guide endpoint and install flow**

In `docs/onboarding/human-guide.md`, ensure `## Before You Start` says:

```markdown
This guide assumes your project runs somewhere other than `hp-15`. That is the normal colleague onboarding path.

For the current HP-15 Ops Board deployment, use this OTLP endpoint from your project:

```text
http://hp-15:4318
```

Use `localhost:4318` only when the code being instrumented runs directly on `hp-15` itself.
```

Replace the helper setup section with:

```markdown
## Python Package Setup

Ops Board provides a small Python helper package. Add it to your project:

```bash
uv add "ops-board-observe @ git+https://github.com/Wenjun-Mao/ops-board.git#subdirectory=packages/ops-board-observe"
```

To remove Ops Board later:

```bash
uv remove ops-board-observe
```

Then import it from your project:

```python
from ops_board_observe import bootstrap_observability, observe
```
```

Ensure the script/job example uses `from ops_board_observe import ...`, `bootstrap_observability()`, and environment variables including:

```dotenv
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
```

- [ ] **Step 2: Update Codex guide**

In `docs/onboarding/codex-guide.md`, remove all instructions to copy/adapt `examples/onboarding/shared/ops_observe.py`. Replace dependency guidance with:

```markdown
Add the package to the target Python project:

```bash
uv add "ops-board-observe @ git+https://github.com/Wenjun-Mao/ops-board.git#subdirectory=packages/ops-board-observe"
```

The package owns the OpenTelemetry, PyYAML, `pydantic-settings`, and `tenacity` dependencies needed by the helper. Do not add those transitive dependencies manually unless the target project already uses them directly.
```

Ensure all target project examples use:

```python
from ops_board_observe import bootstrap_observability, observe
```

and:

```dotenv
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
```

- [ ] **Step 3: Update onboarding contract**

In `docs/onboarding/onboarding-contract.md`, make `http://hp-15:4318` the first OTLP example. Add this paragraph under Python environment variables:

```markdown
The v1 Python integration contract is the `ops-board-observe` package. Projects install it as one dependency and import `ops_board_observe`. They should not copy helper files from the playground.
```

Ensure config examples use:

```yaml
ops_board:
  otlp_endpoint: http://hp-15:4318
```

and:

```dotenv
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
```

- [ ] **Step 4: Update playground README**

In `examples/onboarding/README.md`, replace the helper wording with:

```markdown
The playground consumes `ops-board-observe` through a local path dependency. That keeps the demo aligned with the package colleagues install in real projects.
```

Keep playground-specific `localhost` and `host.docker.internal` examples where they describe the local demo runtime, but say real projects should use `docs/onboarding/human-guide.md` and `OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318`.

- [ ] **Step 5: Update monitoring manual endpoint table**

In `docs/monitoring/ops-board-user-manual.md`, use this table:

```markdown
| Tool | Tailnet URL | Local URL on Ops Board host |
|------|-------------|-----------------------------|
| Homepage | `http://hp-15:3000` | `http://localhost:3000` |
| Uptime Kuma | `http://hp-15:3001` | `http://localhost:3001` |
| SigNoz | `http://hp-15:8080` | `http://localhost:8080` |
| Plane | `http://hp-15:8082` | `http://localhost:8082` |
| OTLP HTTP | `http://hp-15:4318` | `http://localhost:4318` |
```

Add:

```markdown
Use tailnet URLs from colleague machines and onboarded project hosts. Use `localhost` only from a shell or browser running directly on `hp-15`.
```

- [ ] **Step 6: Verify docs no longer teach manual helper copying**

Run:

```bash
rg -n "copy or adapt|shared\\.ops_observe|manually install|localhost:4318" docs/onboarding examples/onboarding docs/monitoring -g "*.md"
```

Expected:

- No `shared.ops_observe` hits outside historical `docs/superpowers`.
- No colleague-facing instruction to copy helper files.
- Any `localhost:4318` hit explicitly says it is only for code running directly on `hp-15` or playground-local checks.

- [ ] **Step 7: Commit package-first docs**

```bash
git add docs/onboarding/human-guide.md docs/onboarding/codex-guide.md docs/onboarding/onboarding-contract.md examples/onboarding/README.md docs/monitoring/ops-board-user-manual.md
git commit -m "docs: document package-first onboarding"
```

## Task 6: Full Verification And Final Push

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run package tests**

```bash
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests -q
```

Expected: PASS.

- [ ] **Step 2: Run playground tests**

```bash
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -q
```

Expected: PASS.

- [ ] **Step 3: Run compose validation**

```bash
docker compose -f examples/onboarding/compose.yaml config --quiet
```

Expected: exit 0.

- [ ] **Step 4: Run doc hygiene checks**

```bash
git diff --check
rg -n "docs/adr/000|docs\\\\adr\\\\000|000[1-9]-|Create the first Uptime|stores SQLite|SQLite data|init-local-config\\.ps1|status\\.ps1|update-stack\\.ps1|bootstrap-uptime-kuma\\.ps1|smoke-day1\\.ps1|Invoke-WebRequest|\\$env:|```powershell|Close SigNoz account registration" README.md docs access scripts stacks examples -g "*.md" -g "!docs/superpowers/**"
```

Expected: `git diff --check` exits 0. The `rg` command may show intentional PowerShell compatibility/backup sections in `README.md` and `scripts/README.md`; it must not show stale onboarding guidance.

- [ ] **Step 5: Commit any missed verification-only fixes**

If verification required small fixes, commit them:

```bash
git add <fixed-files>
git commit -m "fix: align observe package verification"
```

If no fixes were needed, skip this step.

- [ ] **Step 6: Push the branch**

```bash
git status --short --branch
git push
```

Expected: `main` pushes successfully and `git status --short --branch` is clean afterward.

## Self-Review

Spec coverage:

- Package exists under `packages/ops-board-observe`: Tasks 1 and 2.
- Package owns helper dependencies: Task 1 and Task 3 dependency cleanup.
- Colleague install/offboard flow: Task 5 docs.
- Playground consumes package as real consumer: Tasks 3 and 4.
- Reader-facing docs default to `hp-15`: Task 5.
- Tests cover config precedence, endpoint suffixes, observe success/failure, sync/async: Tasks 1 and 2.

Placeholder scan:

- No `TODO` or `TBD` placeholders.
- No "implement later" steps.
- All commands have expected outcomes.

Type consistency:

- Distribution name is `ops-board-observe`.
- Import package is `ops_board_observe`.
- Public exports are `OpsBoardSettings`, `bootstrap_observability`, `load_settings`, and `observe`.

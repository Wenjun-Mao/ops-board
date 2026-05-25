# Ops Board Onboarding System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable onboarding playground plus operator, human, and Codex-facing manuals so Python jobs and APIs can be connected to Ops Board through Tailscale and SigNoz/Uptime Kuma.

**Architecture:** Keep the examples inside `examples/onboarding/` with a tiny local `shared/ops_observe.py` helper that prototypes a future Python onboarding package. The helper provides config loading, OpenTelemetry bootstrap, and an `@observe` decorator; `dummy-job` and `dummy-api` consume it through local imports. Docs under `docs/monitoring/` and `docs/onboarding/` explain how to use Ops Board and how to onboard other projects.

**Tech Stack:** Python 3.12, uv, pytest, pydantic-settings, PyYAML, OpenTelemetry Python SDK/exporters, FastAPI, Uvicorn, tenacity, Docker Compose, Markdown.

---

## Source Notes

- Approved design spec: `docs/superpowers/specs/2026-05-24-ops-board-onboarding-system-design.md`.
- SigNoz collector already publishes OTLP HTTP on `${SIGNOZ_OTLP_HTTP_PORT:-4318}` and collector health on `${SIGNOZ_COLLECTOR_HEALTH_PORT:-13133}`.
- OpenTelemetry Python current docs show `TracerProvider`, `Resource`, `BatchSpanProcessor`, OTLP HTTP span exporters, span attributes, exception recording, and `OTEL_*` environment variables.
- FastAPI current docs show minimal `FastAPI()` app creation and `fastapi.testclient.TestClient` tests.
- Project standards require Python 3.12+, `uv`, `pytest`, `pydantic-settings`, Docker BuildKit cache mounts, descriptive modules, and `tenacity` for flaky network or external I/O operations.

---

## File Structure

Create these paths:

- `examples/onboarding/README.md` - entrypoint for the playground.
- `examples/onboarding/pyproject.toml` - shared local test/dev environment for the helper and examples.
- `examples/onboarding/compose.yaml` - optional Compose runner for dummy API and dummy job.
- `examples/onboarding/config/ops-board.example.yaml` - copyable app-side config contract example.
- `examples/onboarding/shared/__init__.py` - public local helper exports.
- `examples/onboarding/shared/ops_observe.py` - settings loader, bootstrap, and decorator prototype.
- `examples/onboarding/tests/test_ops_observe.py` - helper tests.
- `examples/onboarding/dummy-job/Dockerfile` - Docker image for script-style job example.
- `examples/onboarding/dummy-job/README.md` - job-specific usage.
- `examples/onboarding/dummy-job/job.py` - observed dummy job.
- `examples/onboarding/dummy-job/pyproject.toml` - job runtime dependencies.
- `examples/onboarding/dummy-job/tests/test_job.py` - job tests.
- `examples/onboarding/dummy-api/Dockerfile` - Docker image for API example.
- `examples/onboarding/dummy-api/README.md` - API-specific usage.
- `examples/onboarding/dummy-api/app.py` - observed FastAPI app.
- `examples/onboarding/dummy-api/pyproject.toml` - API runtime dependencies.
- `examples/onboarding/dummy-api/tests/test_app.py` - API tests.
- `docs/monitoring/ops-board-user-manual.md` - operator manual.
- `docs/monitoring/images/README.md` - monitoring screenshot source notes.
- `docs/onboarding/onboarding-contract.md` - stable onboarding contract.
- `docs/onboarding/human-guide.md` - colleague-friendly why and how guide.
- `docs/onboarding/codex-guide.md` - machine-friendly onboarding instructions.
- `docs/onboarding/images/README.md` - onboarding screenshot source notes.

Modify these paths:

- `README.md` - link to the new manuals and playground.

Out of scope for this plan:

- Publishing a Python package.
- Automatic Uptime Kuma monitor creation.
- Automatic discovery of all Tailscale machines.
- Custom SigNoz dashboards.
- Full framework integrations for FastAPI, Flask, Django, Celery, APScheduler, or workers beyond the examples here.

---

## Implementation Tasks

### Task 1: Add Onboarding Contract And Shared Example Config

**Files:**
- Create: `docs/onboarding/onboarding-contract.md`
- Create: `examples/onboarding/config/ops-board.example.yaml`
- Create: `examples/onboarding/README.md`
- Create: `docs/onboarding/images/README.md`
- Create: `docs/monitoring/images/README.md`

- [ ] **Step 1: Create the onboarding contract**

Create `docs/onboarding/onboarding-contract.md`:

````markdown
# Ops Board Onboarding Contract

This contract defines what it means for a project to be onboarded to Ops Board.

Ops Board is the private operating center for services and jobs that run across local computers, VPSs, and cloud providers. Tailscale is the network boundary for v1. Public reverse proxy access is intentionally deferred.

## Required Identity

Every onboarded project must define:

| Field | Required | Example | Notes |
|-------|----------|---------|-------|
| `service.name` | Yes | `billing-api` | Stable service name used in SigNoz and docs. |
| `service.namespace` | Yes | `content-shuttle` | Project group, client group, or repo family. |
| `deployment.environment` | Yes | `local`, `staging`, `prod` | Keep values short and consistent. |
| `owner` | Yes | `mk`, `ops`, `data-team` | Person or team responsible for first response. |
| `runtime.host` | Yes | `hu-workstation` | Hostname or VPS name where the project runs. |
| `tailscale.host` | Recommended | `hu-workstation.tailnet-name.ts.net` | Use when the service is reachable through Tailscale. |
| `runtime.provider` | Optional | `local`, `hetzner`, `aws` | Useful when projects span providers. |
| `runtime.country` | Optional | `CA`, `US`, `JP` | Useful when latency or data location matters. |

## Required Signals

Every onboarded project should expose or emit:

| Signal | Tool | Required | Purpose |
|--------|------|----------|---------|
| Health endpoint | Uptime Kuma | Yes for services, recommended for long-running workers | Answers whether it is alive right now. |
| Traces | SigNoz | Yes for APIs and important jobs | Shows what happened inside a request or job run. |
| Logs | SigNoz or Docker logs | Recommended | Provides context around failures and important events. |
| Metrics | SigNoz | Optional for v1 | Useful after the basic health/tracing flow works. |
| Operator links | Homepage | Recommended | Gives teammates one place to start. |
| Follow-up tasks | Plane | Optional | Tracks work after an issue becomes actionable. |

## Endpoint Conventions

For local testing on the Ops Board host:

```text
SigNoz UI:          http://localhost:8080
OTLP HTTP:         http://localhost:4318
OTLP gRPC:         http://localhost:4317
Collector health:  http://localhost:13133
Uptime Kuma:       http://localhost:3001
Homepage:          http://localhost:3000
Plane:             http://localhost:8082
```

For other tailnet machines, replace `localhost` with the Ops Board host's Tailscale MagicDNS name or Tailscale IP.

## App Config Shape

Projects should be able to express onboarding config in this shape:

```yaml
service:
  name: example-api
  namespace: ops-board.examples
  environment: local
  owner: mk
  version: 0.1.0

runtime:
  host: example-host
  tailscale_host: example-host.tailnet-name.ts.net
  provider: local
  country: CA

ops_board:
  otlp_endpoint: http://localhost:4318
  health_url: http://localhost:8000/health
```

## Python Environment Variable Conventions

Python projects using the v1 helper use the `OPS_BOARD_` prefix:

```dotenv
OPS_BOARD_SERVICE_NAME=example-api
OPS_BOARD_SERVICE_NAMESPACE=ops-board.examples
OPS_BOARD_ENVIRONMENT=local
OPS_BOARD_OWNER=mk
OPS_BOARD_OTLP_ENDPOINT=http://localhost:4318
OPS_BOARD_HEALTH_URL=http://localhost:8000/health
OPS_BOARD_CONFIG_FILE=ops-board.yaml
OPS_BOARD_SECRETS_DIR=/run/secrets
```

The helper also sets standard OpenTelemetry resource attributes in process. Projects may still use standard `OTEL_*` variables when they outgrow the helper.

## Python Helper Precedence

The v1 helper loads config in this order:

1. Explicit function arguments
2. Docker secret files from `OPS_BOARD_SECRETS_DIR` or `/run/secrets`
3. `OPS_BOARD_*` environment variables
4. YAML config file
5. Defaults

Secret files use lower-case field names, for example:

```text
/run/secrets/service_name
/run/secrets/owner
/run/secrets/otlp_endpoint
```

## Acceptance Checklist

A project is onboarded when all required items are true:

- It has a stable service name, namespace, environment, and owner.
- It documents where it runs and how it reaches Ops Board over Tailscale.
- A long-running service exposes a health endpoint.
- Uptime Kuma can monitor that health endpoint.
- A Python job or key function emits an observed span with success/failure status.
- A web/API service emits request-level traces or observed key-function spans.
- Logs include enough context to identify service, host, environment, and run/request.
- A teammate can find the project from docs or Homepage.
````

- [ ] **Step 2: Create the shared example config file**

Create `examples/onboarding/config/ops-board.example.yaml`:

```yaml
service:
  name: dummy-api
  namespace: ops-board.examples
  environment: local
  owner: mk
  version: 0.1.0

runtime:
  host: localhost
  tailscale_host: localhost
  provider: local
  country: CA

ops_board:
  otlp_endpoint: http://localhost:4318
  health_url: http://localhost:8000/health
```

- [ ] **Step 3: Create the playground README**

Create `examples/onboarding/README.md`:

````markdown
# Ops Board Onboarding Playground

This playground gives Ops Board a small local project to monitor before real projects are onboarded.

It covers two common shapes:

- `dummy-job`: a scheduled or script-style Python job.
- `dummy-api`: a Python web/API service with `/health`.

Both examples use `shared/ops_observe.py`, a tiny local helper that prototypes a future Python onboarding library.

## Prerequisites

From the repo root:

```powershell
.\scripts\init-local-config.ps1
docker compose --env-file .env -f compose.yaml up -d
```

Verify the collector is reachable:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:13133/ -TimeoutSec 20
```

Expected: HTTP `200`.

## Local Python Test Run

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
```

Expected: all tests pass.

## Run The Dummy Job Locally

```powershell
$env:OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-job python examples/onboarding/dummy-job/job.py
```

Expected: the command prints a successful job summary and emits an OpenTelemetry span to SigNoz when the collector is running.

## Run The Dummy API Locally

```powershell
$env:OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-api uvicorn app:app --app-dir examples/onboarding/dummy-api --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/health
http://localhost:8000/work/demo
```

## Run With Docker Compose

```powershell
docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

Expected:

- `dummy-api` is reachable at `http://localhost:8000/health`.
- `dummy-job` exits `0`.
- SigNoz shows services named `dummy-api` and `dummy-job`.

## Tailscale Notes

When a monitored project runs on another tailnet machine, set `OPS_BOARD_OTLP_ENDPOINT` to the Ops Board host's private address:

```powershell
$env:OPS_BOARD_OTLP_ENDPOINT="http://<ops-board-tailscale-hostname>:4318"
```
````

- [ ] **Step 4: Create image source note files**

Create `docs/onboarding/images/README.md`:

```markdown
# Onboarding Images

Prefer local screenshots captured from the running Ops Board stack and onboarding playground.

Planned captures:

- `dummy-api-health.png`: browser view of `http://localhost:8000/health`.
- `dummy-api-work.png`: browser view of `http://localhost:8000/work/demo`.
- `signoz-dummy-api-traces.png`: SigNoz traces view filtered to `dummy-api`.
- `signoz-dummy-job-traces.png`: SigNoz traces view filtered to `dummy-job`.

If an external official visual is used, add the source URL and capture date beside the image reference in the manual that uses it.
```

Create `docs/monitoring/images/README.md`:

```markdown
# Monitoring Images

Prefer local screenshots captured from the running Ops Board stack.

Planned captures:

- `homepage-overview.png`: Homepage landing view.
- `uptime-kuma-dashboard.png`: Uptime Kuma monitor list or status page.
- `signoz-services.png`: SigNoz services view.
- `signoz-traces.png`: SigNoz traces view.
- `plane-board.png`: Plane board or first-run project view.

If an external official visual is used, add the source URL and capture date beside the image reference in the manual that uses it.
```

- [ ] **Step 5: Verify the docs contain no unresolved markers**

Run:

```powershell
Select-String -Path docs/onboarding/onboarding-contract.md,examples/onboarding/README.md,docs/onboarding/images/README.md,docs/monitoring/images/README.md -Pattern "UNRESOLVED|FIXME|\\?\\?"
git diff --check
```

Expected:

- `Select-String` prints no matches.
- `git diff --check` exits `0`.

- [ ] **Step 6: Commit contract and config**

```powershell
git add docs/onboarding/onboarding-contract.md docs/onboarding/images/README.md docs/monitoring/images/README.md examples/onboarding/README.md examples/onboarding/config/ops-board.example.yaml
git commit -m "docs: add ops-board onboarding contract"
```

---

### Task 2: Add Shared Python Helper With Tests

**Files:**
- Create: `examples/onboarding/pyproject.toml`
- Create: `examples/onboarding/shared/__init__.py`
- Create: `examples/onboarding/shared/ops_observe.py`
- Create: `examples/onboarding/tests/test_ops_observe.py`

- [ ] **Step 1: Create the playground test environment**

Create `examples/onboarding/pyproject.toml`:

```toml
[project]
name = "ops-board-onboarding-playground"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.128.0",
  "httpx>=0.28.0",
  "loguru>=0.7.3",
  "opentelemetry-api>=1.39.0",
  "opentelemetry-exporter-otlp-proto-http>=1.39.0",
  "opentelemetry-sdk>=1.39.0",
  "pydantic>=2.12.0",
  "pydantic-settings>=2.12.0",
  "pytest>=9.0.0",
  "pyyaml>=6.0.2",
  "tenacity>=9.1.0",
  "uvicorn[standard]>=0.38.0",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = [
  "tests",
  "dummy-job/tests",
  "dummy-api/tests",
]
```

- [ ] **Step 2: Write failing tests for config precedence and decorator behavior**

Create `examples/onboarding/tests/test_ops_observe.py`:

```python
from __future__ import annotations

import pytest

from shared.ops_observe import observe, load_settings


def test_load_settings_precedence(tmp_path, monkeypatch):
    config_file = tmp_path / "ops-board.yaml"
    config_file.write_text(
        """
service:
  name: config-service
  namespace: config-namespace
  environment: config-env
  owner: config-owner
runtime:
  host: config-host
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

    settings = load_settings(
        config_path=config_file,
        service_namespace="arg-namespace",
    )

    assert settings.service_name == "secret-service"
    assert settings.service_namespace == "arg-namespace"
    assert settings.environment == "env"
    assert settings.owner == "env-owner"
    assert settings.runtime_host == "config-host"
    assert settings.otlp_endpoint == "http://config-collector:4318"
    assert settings.health_url == "http://config-service:8000/health"


def test_observe_returns_wrapped_function_result():
    @observe("unit.success")
    def add(left: int, right: int) -> int:
        return left + right

    assert add(2, 3) == 5


def test_observe_records_and_reraises_exceptions():
    @observe("unit.failure")
    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        fail()
```

- [ ] **Step 3: Run tests and confirm they fail because the helper does not exist**

Run:

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests/test_ops_observe.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'shared'` or `No module named 'shared.ops_observe'`.

- [ ] **Step 4: Add public helper exports**

Create `examples/onboarding/shared/__init__.py`:

```python
from .ops_observe import OpsBoardSettings, bootstrap_observability, load_settings, observe

__all__ = [
    "OpsBoardSettings",
    "bootstrap_observability",
    "load_settings",
    "observe",
]
```

- [ ] **Step 5: Add the helper implementation**

Create `examples/onboarding/shared/ops_observe.py`:

```python
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
from opentelemetry.trace import Status, StatusCode
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
        secrets_dir="/run/secrets",
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
    span: trace.Span,
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
```

- [ ] **Step 6: Run helper tests and confirm they pass**

Run:

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests/test_ops_observe.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Lock the playground dependencies**

Run:

```powershell
uv lock --project examples/onboarding
```

Expected: `examples/onboarding/uv.lock` is created or updated.

- [ ] **Step 8: Commit the helper**

```powershell
git add examples/onboarding/pyproject.toml examples/onboarding/uv.lock examples/onboarding/shared examples/onboarding/tests/test_ops_observe.py
git commit -m "feat: add onboarding observability helper"
```

---

### Task 3: Add Dummy Script-Style Job

**Files:**
- Create: `examples/onboarding/dummy-job/pyproject.toml`
- Create: `examples/onboarding/dummy-job/job.py`
- Create: `examples/onboarding/dummy-job/tests/test_job.py`
- Create: `examples/onboarding/dummy-job/Dockerfile`
- Create: `examples/onboarding/dummy-job/README.md`

- [ ] **Step 1: Create the dummy job project file**

Create `examples/onboarding/dummy-job/pyproject.toml`:

```toml
[project]
name = "ops-board-dummy-job"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "loguru>=0.7.3",
  "opentelemetry-api>=1.39.0",
  "opentelemetry-exporter-otlp-proto-http>=1.39.0",
  "opentelemetry-sdk>=1.39.0",
  "pydantic>=2.12.0",
  "pydantic-settings>=2.12.0",
  "pytest>=9.0.0",
  "pyyaml>=6.0.2",
  "tenacity>=9.1.0",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["..", "."]
testpaths = ["tests"]
```

- [ ] **Step 2: Write failing job tests**

Create `examples/onboarding/dummy-job/tests/test_job.py`:

```python
from __future__ import annotations

from job import build_job_summary, run_job


def test_build_job_summary_contains_status_and_record_count():
    summary = build_job_summary(records_processed=3, status="success")

    assert summary == {
        "status": "success",
        "records_processed": 3,
        "job_name": "dummy-nightly-import",
    }


def test_run_job_returns_success_summary(monkeypatch):
    monkeypatch.setenv("OPS_BOARD_SERVICE_NAME", "dummy-job-test")

    summary = run_job(records=2, export=False)

    assert summary["status"] == "success"
    assert summary["records_processed"] == 2
```

- [ ] **Step 3: Run job tests and confirm they fail because `job.py` does not exist**

Run:

```powershell
uv run --project examples/onboarding/dummy-job pytest examples/onboarding/dummy-job/tests/test_job.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'job'`.

- [ ] **Step 4: Add the dummy job implementation**

Create `examples/onboarding/dummy-job/job.py`:

```python
from __future__ import annotations

import logging
import random
import time

from tenacity import retry, stop_after_attempt, wait_exponential

from shared.ops_observe import bootstrap_observability, observe

LOGGER = logging.getLogger("ops_board.dummy_job")
JOB_NAME = "dummy-nightly-import"


def build_job_summary(records_processed: int, status: str) -> dict[str, int | str]:
    return {
        "status": status,
        "records_processed": records_processed,
        "job_name": JOB_NAME,
    }


@retry(wait=wait_exponential(multiplier=0.1, min=0.1, max=1), stop=stop_after_attempt(3))
def simulate_flaky_external_read(record_id: int) -> dict[str, int | str]:
    if record_id == 1 and random.random() < 0.05:
        raise RuntimeError("simulated temporary upstream read failure")
    return {"record_id": record_id, "value": f"record-{record_id}"}


@observe("dummy-job.process-record")
def process_record(record_id: int) -> dict[str, int | str]:
    record = simulate_flaky_external_read(record_id)
    time.sleep(0.05)
    LOGGER.info("dummy_job_record_processed", extra={"record_id": record_id})
    return record


@observe("dummy-job.run")
def run_job(records: int = 5, *, export: bool = True) -> dict[str, int | str]:
    bootstrap_observability(
        export=export,
        service_name="dummy-job",
        service_namespace="ops-board.examples",
        owner="mk",
    )
    processed = 0
    for record_id in range(records):
        process_record(record_id)
        processed += 1

    summary = build_job_summary(records_processed=processed, status="success")
    LOGGER.info("dummy_job_completed", extra=summary)
    return summary


def main() -> None:
    summary = run_job()
    print(summary)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run job tests and confirm they pass**

Run:

```powershell
uv run --project examples/onboarding/dummy-job pytest examples/onboarding/dummy-job/tests/test_job.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Add the dummy job Dockerfile with uv cache mounts**

Create `examples/onboarding/dummy-job/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /uvx /bin/

WORKDIR /app

COPY dummy-job/pyproject.toml ./pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv uv sync --no-dev --no-install-project

COPY shared ./shared
COPY dummy-job/job.py ./job.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["uv", "run", "python", "job.py"]
```

- [ ] **Step 7: Add the dummy job README**

Create `examples/onboarding/dummy-job/README.md`:

````markdown
# Dummy Job

This example represents a scheduled script, cron job, batch import, or one-off worker.

It demonstrates:

- `bootstrap_observability(...)` for service identity and OTLP export.
- `@observe(...)` around the job run and per-record processing.
- `tenacity` around simulated flaky external I/O.
- Structured log fields through Python logging `extra`.

## Run Locally

From the repo root:

```powershell
$env:OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-job python examples/onboarding/dummy-job/job.py
```

Expected: the command prints a success summary.

## Run Tests

```powershell
uv run --project examples/onboarding/dummy-job pytest examples/onboarding/dummy-job/tests -v
```

## Run In Docker

```powershell
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```
````

- [ ] **Step 8: Lock dummy job dependencies**

Run:

```powershell
uv lock --project examples/onboarding/dummy-job
```

Expected: `examples/onboarding/dummy-job/uv.lock` is created or updated.

- [ ] **Step 9: Commit the dummy job**

```powershell
git add examples/onboarding/dummy-job
git commit -m "feat: add observed dummy job"
```

---

### Task 4: Add Dummy FastAPI Service

**Files:**
- Create: `examples/onboarding/dummy-api/pyproject.toml`
- Create: `examples/onboarding/dummy-api/app.py`
- Create: `examples/onboarding/dummy-api/tests/test_app.py`
- Create: `examples/onboarding/dummy-api/Dockerfile`
- Create: `examples/onboarding/dummy-api/README.md`

- [ ] **Step 1: Create the dummy API project file**

Create `examples/onboarding/dummy-api/pyproject.toml`:

```toml
[project]
name = "ops-board-dummy-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.128.0",
  "httpx>=0.28.0",
  "loguru>=0.7.3",
  "opentelemetry-api>=1.39.0",
  "opentelemetry-exporter-otlp-proto-http>=1.39.0",
  "opentelemetry-sdk>=1.39.0",
  "pydantic>=2.12.0",
  "pydantic-settings>=2.12.0",
  "pytest>=9.0.0",
  "pyyaml>=6.0.2",
  "tenacity>=9.1.0",
  "uvicorn[standard]>=0.38.0",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["..", "."]
testpaths = ["tests"]
```

- [ ] **Step 2: Write failing API tests**

Create `examples/onboarding/dummy-api/tests/test_app.py`:

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app import app, expensive_lookup

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "dummy-api"


def test_work_endpoint_returns_demo_payload():
    response = client.get("/work/demo")

    assert response.status_code == 200
    assert response.json()["item_id"] == "demo"
    assert response.json()["status"] == "processed"


def test_expensive_lookup_is_deterministic():
    assert expensive_lookup("abc") == {"item_id": "abc", "score": 294}
```

- [ ] **Step 3: Run API tests and confirm they fail because `app.py` does not exist**

Run:

```powershell
uv run --project examples/onboarding/dummy-api pytest examples/onboarding/dummy-api/tests/test_app.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 4: Add the dummy API implementation**

Create `examples/onboarding/dummy-api/app.py`:

```python
from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.ops_observe import bootstrap_observability, observe

LOGGER = logging.getLogger("ops_board.dummy_api")

settings = bootstrap_observability(
    service_name="dummy-api",
    service_namespace="ops-board.examples",
    owner="mk",
)

app = FastAPI(title="Ops Board Dummy API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@retry(wait=wait_exponential(multiplier=0.1, min=0.1, max=1), stop=stop_after_attempt(3))
def simulated_external_dependency(item_id: str) -> dict[str, str]:
    return {"item_id": item_id, "source": "simulated-upstream"}


@observe("dummy-api.expensive-lookup")
def expensive_lookup(item_id: str) -> dict[str, int | str]:
    simulated_external_dependency(item_id)
    time.sleep(0.05)
    score = sum(ord(character) for character in item_id)
    LOGGER.info("dummy_api_lookup_completed", extra={"item_id": item_id, "score": score})
    return {"item_id": item_id, "score": score}


@app.get("/work/{item_id}")
@observe("dummy-api.work")
def run_work(item_id: str) -> dict[str, int | str]:
    result = expensive_lookup(item_id)
    return {
        "item_id": item_id,
        "status": "processed",
        "score": result["score"],
    }
```

- [ ] **Step 5: Run API tests and confirm they pass**

Run:

```powershell
uv run --project examples/onboarding/dummy-api pytest examples/onboarding/dummy-api/tests/test_app.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Add the dummy API Dockerfile with uv cache mounts**

Create `examples/onboarding/dummy-api/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /uvx /bin/

WORKDIR /app

COPY dummy-api/pyproject.toml ./pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv uv sync --no-dev --no-install-project

COPY shared ./shared
COPY dummy-api/app.py ./app.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Add the dummy API README**

Create `examples/onboarding/dummy-api/README.md`:

````markdown
# Dummy API

This example represents a Python web/API service.

It demonstrates:

- `/health` for Uptime Kuma.
- `@observe(...)` around a request handler and a key internal function.
- `tenacity` around simulated external I/O.
- OpenTelemetry export to the Ops Board SigNoz collector.

## Run Locally

From the repo root:

```powershell
$env:OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-api uvicorn app:app --app-dir examples/onboarding/dummy-api --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/health
http://localhost:8000/work/demo
```

## Run Tests

```powershell
uv run --project examples/onboarding/dummy-api pytest examples/onboarding/dummy-api/tests -v
```

## Run In Docker

```powershell
docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
```
````

- [ ] **Step 8: Lock dummy API dependencies**

Run:

```powershell
uv lock --project examples/onboarding/dummy-api
```

Expected: `examples/onboarding/dummy-api/uv.lock` is created or updated.

- [ ] **Step 9: Commit the dummy API**

```powershell
git add examples/onboarding/dummy-api
git commit -m "feat: add observed dummy api"
```

---

### Task 5: Add Compose Runner And Runtime Verification

**Files:**
- Create: `examples/onboarding/compose.yaml`
- Modify: `examples/onboarding/README.md`

- [ ] **Step 1: Create the onboarding Compose file**

Create `examples/onboarding/compose.yaml`:

```yaml
name: ops-board-onboarding

services:
  dummy-api:
    build:
      context: .
      dockerfile: dummy-api/Dockerfile
    container_name: ops-board-dummy-api
    restart: unless-stopped
    ports:
      - "0.0.0.0:${DUMMY_API_PORT:-8000}:8000"
    environment:
      OPS_BOARD_SERVICE_NAME: dummy-api
      OPS_BOARD_SERVICE_NAMESPACE: ops-board.examples
      OPS_BOARD_ENVIRONMENT: local
      OPS_BOARD_OWNER: mk
      OPS_BOARD_RUNTIME_HOST: docker
      OPS_BOARD_OTLP_ENDPOINT: http://host.docker.internal:4318
      OPS_BOARD_HEALTH_URL: http://localhost:8000/health
    extra_hosts:
      - "host.docker.internal:host-gateway"

  dummy-job:
    build:
      context: .
      dockerfile: dummy-job/Dockerfile
    container_name: ops-board-dummy-job
    restart: "no"
    environment:
      OPS_BOARD_SERVICE_NAME: dummy-job
      OPS_BOARD_SERVICE_NAMESPACE: ops-board.examples
      OPS_BOARD_ENVIRONMENT: local
      OPS_BOARD_OWNER: mk
      OPS_BOARD_RUNTIME_HOST: docker
      OPS_BOARD_OTLP_ENDPOINT: http://host.docker.internal:4318
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

- [ ] **Step 2: Validate Compose config**

Run:

```powershell
docker compose -f examples/onboarding/compose.yaml config --quiet
```

Expected: exits `0`.

- [ ] **Step 3: Run the full Python test suite**

Run:

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
```

Expected: all tests pass.

- [ ] **Step 4: Build both example images**

Run:

```powershell
docker compose -f examples/onboarding/compose.yaml build
```

Expected: both images build successfully and Docker BuildKit cache mount steps are used during dependency sync.

- [ ] **Step 5: Start the Ops Board stack**

Run:

```powershell
docker compose --env-file .env -f compose.yaml up -d
```

Expected: Ops Board starts or remains running.

- [ ] **Step 6: Verify the SigNoz collector is reachable before sending telemetry**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:13133/ -TimeoutSec 20
```

Expected: HTTP `200`.

- [ ] **Step 7: Start dummy API and call it**

Run:

```powershell
docker compose -f examples/onboarding/compose.yaml up -d dummy-api
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:8000/work/demo -TimeoutSec 20
```

Expected:

- `/health` returns JSON with `"status":"ok"`.
- `/work/demo` returns JSON with `"status":"processed"`.

- [ ] **Step 8: Run dummy job in a one-shot container**

Run:

```powershell
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

Expected: command exits `0` and prints a success summary with `job_name` equal to `dummy-nightly-import`.

- [ ] **Step 9: Confirm telemetry containers stay clean enough for v1**

Run:

```powershell
docker compose -f examples/onboarding/compose.yaml logs --tail=100 dummy-api
docker compose --env-file .env -f compose.yaml logs --tail=100 otel-collector
```

Expected:

- `dummy-api` logs show health/work calls.
- `otel-collector` logs do not show repeated export errors for `dummy-api` or `dummy-job`.

- [ ] **Step 10: Add runtime verification notes to the playground README**

Append this section to `examples/onboarding/README.md`:

````markdown
## Verify In SigNoz

After calling the API and running the job, open SigNoz:

```text
http://localhost:8080
```

Look for these service names:

```text
dummy-api
dummy-job
```

Useful first checks:

- Services view includes `dummy-api` after `/work/demo` is called.
- Traces include spans named `dummy-api.work` and `dummy-api.expensive-lookup`.
- Traces include spans named `dummy-job.run` and `dummy-job.process-record`.
- Logs are present if OTLP log export is accepted by the collector.

If the project runs on another tailnet machine, set:

```dotenv
OPS_BOARD_OTLP_ENDPOINT=http://<ops-board-tailscale-hostname>:4318
```
````

- [ ] **Step 11: Commit Compose runner**

```powershell
git add examples/onboarding/compose.yaml examples/onboarding/README.md
git commit -m "feat: add onboarding playground compose runner"
```

---

### Task 6: Write Operator And Human Manuals

**Files:**
- Create: `docs/monitoring/ops-board-user-manual.md`
- Create: `docs/onboarding/human-guide.md`
- Modify: `README.md`

- [ ] **Step 1: Create the Ops Board user manual**

Create `docs/monitoring/ops-board-user-manual.md`:

````markdown
# Ops Board User Manual

Ops Board is a private operations board for projects that run across local machines, VPSs, countries, and cloud providers.

Use it when you need to answer:

- What projects exist and where do I start?
- Is a project alive right now?
- What happened inside a job, API request, or service?
- Who owns the project and where does it run?
- What follow-up work should be tracked?

Tailscale is the access layer for v1. Do not expose dashboards publicly unless the access model is intentionally changed.

## Where To Start

Start with Homepage:

```text
http://localhost:3000
http://<ops-board-tailscale-hostname>:3000
```

Homepage should link to:

- SigNoz
- Uptime Kuma
- Plane
- Ops Board docs

## Which Tool To Use

| Need | Use | Why |
|------|-----|-----|
| Find services and dashboards | Homepage | It is the launch board. |
| Check whether something is up | Uptime Kuma | It tracks health endpoints and status pages. |
| Debug a slow API or failed job | SigNoz | It stores traces, logs, and metrics. |
| Track follow-up work | Plane | It turns operational findings into tasks. |
| Reach private hosts | Tailscale | It connects local machines and VPSs privately. |

## Common Workflow: Service Looks Down

1. Open Homepage.
2. Open Uptime Kuma.
3. Check the monitor status and last failure time.
4. Open SigNoz and filter by `service.name`.
5. Look for recent traces, errors, and logs around the failure time.
6. If work is needed, create or update a Plane issue.

## Common Workflow: Job Failed Or Did Not Run

1. Open SigNoz.
2. Search for the job service name, for example `dummy-job`.
3. Look for spans named after the job run.
4. Check span status, exception events, duration, and host attributes.
5. Confirm the expected host and environment match the project docs.

## Current Local Endpoints

| Tool | Local URL | Tailnet URL Pattern |
|------|-----------|---------------------|
| Homepage | `http://localhost:3000` | `http://<host>:3000` |
| Uptime Kuma | `http://localhost:3001` | `http://<host>:3001` |
| SigNoz | `http://localhost:8080` | `http://<host>:8080` |
| Plane | `http://localhost:8082` | `http://<host>:8082` |
| OTLP HTTP | `http://localhost:4318` | `http://<host>:4318` |

## First Dashboards To Check

### Homepage

Use Homepage to confirm the board has links for the tools you expect.

Screenshot target:

```text
docs/monitoring/images/homepage-overview.png
```

### Uptime Kuma

Use Uptime Kuma for health status and status page checks.

Screenshot target:

```text
docs/monitoring/images/uptime-kuma-dashboard.png
```

### SigNoz

Use SigNoz for traces, logs, metrics, and service-level debugging.

Screenshot targets:

```text
docs/monitoring/images/signoz-services.png
docs/monitoring/images/signoz-traces.png
```

### Plane

Use Plane after a monitoring finding becomes work that someone should track.

Screenshot target:

```text
docs/monitoring/images/plane-board.png
```

## Limits Of V1

Ops Board v1 is good enough for pilot onboarding. It is not yet a fully automated monitoring platform.

Current manual steps:

- Create Uptime Kuma monitors manually.
- Capture screenshots manually after UI login where needed.
- Add project entries to Homepage manually.
- Use project docs to track ownership and runtime location.
````

- [ ] **Step 2: Create the colleague-friendly human onboarding guide**

Create `docs/onboarding/human-guide.md`:

````markdown
# Onboarding A Project To Ops Board

This guide is for teammates who want their project to be visible and debuggable in Ops Board.

## Why Use Ops Board

Ops Board gives us one private place to understand project health across local computers, VPSs, cloud providers, and countries.

It helps because:

- We stop guessing where a project runs.
- We can tell whether a service is alive before digging into code.
- We can debug slow APIs and failed jobs through traces and logs.
- We share the same language for service name, environment, owner, health, traces, and runtime host.
- Tailscale keeps access private without exposing dashboards to the public internet.

If your project matters enough that someone would ask "is it working?", it should probably be represented in Ops Board.

## What Onboarding Means

For v1, onboarding means:

- The project has a stable service name.
- The owner and environment are clear.
- The runtime host is documented.
- Long-running services have a health endpoint.
- Uptime Kuma can monitor that health endpoint.
- Python jobs or key functions can emit observed spans.
- SigNoz can show useful traces or logs.

## Before You Start

Collect:

```text
service.name
service.namespace
deployment.environment
owner
runtime host
Tailscale hostname or IP
health endpoint URL
Ops Board OTLP endpoint
```

For local testing, the OTLP endpoint is:

```text
http://localhost:4318
```

For a remote tailnet machine, use:

```text
http://<ops-board-tailscale-hostname>:4318
```

## Python Script Or Scheduled Job

Use the decorator around the important unit of work:

```python
from shared.ops_observe import bootstrap_observability, observe

bootstrap_observability(service_name="my-job", service_namespace="my-project")


@observe("my-job.run")
def run_job() -> None:
    ...
```

Run the job, then check SigNoz for `service.name = my-job`.

## Python Web/API Service

Expose a health endpoint:

```python
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "my-api"}
```

Wrap key handlers or functions:

```python
@observe("my-api.process-request")
def process_request(item_id: str) -> dict[str, str]:
    ...
```

Then add the health URL to Uptime Kuma.

## Dockerized App

Pass config through environment variables:

```yaml
environment:
  OPS_BOARD_SERVICE_NAME: my-api
  OPS_BOARD_SERVICE_NAMESPACE: my-project
  OPS_BOARD_ENVIRONMENT: prod
  OPS_BOARD_OWNER: team-name
  OPS_BOARD_OTLP_ENDPOINT: http://<ops-board-tailscale-hostname>:4318
```

Use Docker logs plus SigNoz traces as the first debugging layer.

## Remote Tailscale Machine

On the remote machine:

1. Join the same tailnet.
2. Confirm it can reach the Ops Board collector.
3. Configure `OPS_BOARD_OTLP_ENDPOINT`.
4. Run the app or job.
5. Check SigNoz from the Ops Board UI.

Health checks can point either from Uptime Kuma to the remote service's tailnet URL, or from the service host back to Ops Board if the service cannot accept inbound checks.

## First Success Test

After onboarding, prove these checks:

```text
Uptime Kuma can see the health endpoint.
SigNoz can see at least one trace from the project.
The docs say who owns the project.
The docs say where the project runs.
```

## Example Playground

Use the local playground before onboarding a real project:

```powershell
docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

Then open SigNoz and look for:

```text
dummy-api
dummy-job
```
````

- [ ] **Step 3: Update the root README with docs links**

Add this section before `## Current Priorities` in `README.md`:

````markdown
## Monitoring And Onboarding Docs

Use these docs when operating the board or connecting projects to it:

- `docs/monitoring/ops-board-user-manual.md` - how to use Ops Board day to day.
- `docs/onboarding/human-guide.md` - why and how colleagues should onboard projects.
- `docs/onboarding/onboarding-contract.md` - stable service identity and telemetry contract.
- `docs/onboarding/codex-guide.md` - machine-friendly onboarding instructions for Codex sessions.
- `examples/onboarding/README.md` - dummy API/job playground for testing the experience.
````

- [ ] **Step 4: Verify docs**

Run:

```powershell
Select-String -Path docs/monitoring/ops-board-user-manual.md,docs/onboarding/human-guide.md,README.md -Pattern "UNRESOLVED|FIXME|\\?\\?"
git diff --check
```

Expected:

- `Select-String` prints no matches.
- `git diff --check` exits `0`.

- [ ] **Step 5: Commit operator and human docs**

```powershell
git add README.md docs/monitoring/ops-board-user-manual.md docs/onboarding/human-guide.md
git commit -m "docs: add ops-board user and human onboarding guides"
```

---

### Task 7: Write Codex Guide And Final Verification

**Files:**
- Create: `docs/onboarding/codex-guide.md`
- Modify: `examples/onboarding/README.md`

- [ ] **Step 1: Create the machine-friendly Codex guide**

Create `docs/onboarding/codex-guide.md`:

````markdown
# Codex Guide: Onboard A Project To Ops Board

Use this guide when another Codex session needs to connect a project to Ops Board.

## Goal

Make the target project visible in Ops Board with a stable service identity, health check, and useful telemetry.

## Do Not Change

- Do not rename the target project.
- Do not rotate production secrets.
- Do not expose Ops Board publicly.
- Do not add a reverse proxy unless explicitly requested.
- Do not rewrite unrelated app architecture.

## Required Inputs

Collect or infer:

```text
service_name
service_namespace
environment
owner
runtime_host
tailscale_host
otlp_endpoint
health_url
```

Use `http://<ops-board-tailscale-hostname>:4318` for remote machines connected through Tailscale.

## Python App Changes

If the target is Python, add dependencies using `uv`:

```powershell
uv add pydantic-settings pyyaml opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http tenacity
```

If it is a FastAPI app, also ensure:

```powershell
uv add fastapi uvicorn
```

Copy or adapt the helper pattern from:

```text
examples/onboarding/shared/ops_observe.py
```

Add config through env vars:

```dotenv
OPS_BOARD_SERVICE_NAME=<service-name>
OPS_BOARD_SERVICE_NAMESPACE=<namespace>
OPS_BOARD_ENVIRONMENT=<environment>
OPS_BOARD_OWNER=<owner>
OPS_BOARD_RUNTIME_HOST=<host>
OPS_BOARD_TAILSCALE_HOST=<tailscale-host>
OPS_BOARD_OTLP_ENDPOINT=http://<ops-board-host>:4318
OPS_BOARD_HEALTH_URL=http://<service-host>:<port>/health
```

## Script Or Scheduled Job Pattern

Add bootstrap once near the entrypoint:

```python
from shared.ops_observe import bootstrap_observability, observe

bootstrap_observability(service_name="<service-name>", service_namespace="<namespace>")
```

Decorate the main work:

```python
@observe("<service-name>.run")
def run_job() -> None:
    ...
```

Network requests or external I/O must use `tenacity` retries:

```python
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(wait=wait_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(3))
def call_external_service() -> str:
    ...
```

## Web/API Pattern

Expose a health endpoint:

```python
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "<service-name>"}
```

Decorate key handlers or functions:

```python
@observe("<service-name>.process")
def process() -> dict[str, str]:
    ...
```

## Docker Compose Pattern

Add these environment variables to the service:

```yaml
environment:
  OPS_BOARD_SERVICE_NAME: <service-name>
  OPS_BOARD_SERVICE_NAMESPACE: <namespace>
  OPS_BOARD_ENVIRONMENT: <environment>
  OPS_BOARD_OWNER: <owner>
  OPS_BOARD_RUNTIME_HOST: <host>
  OPS_BOARD_TAILSCALE_HOST: <tailscale-host>
  OPS_BOARD_OTLP_ENDPOINT: http://<ops-board-host>:4318
  OPS_BOARD_HEALTH_URL: http://<service-host>:<port>/health
```

## Validation Commands

Run project tests:

```powershell
uv run pytest -v
```

Verify health endpoint:

```powershell
Invoke-WebRequest -UseBasicParsing <health-url> -TimeoutSec 20
```

Verify Ops Board collector from the target host:

```powershell
Invoke-WebRequest -UseBasicParsing http://<ops-board-host>:13133/ -TimeoutSec 20
```

Run one request or one job execution, then check SigNoz for:

```text
service.name = <service-name>
deployment.environment = <environment>
```

## Acceptance Criteria

The target project is onboarded when:

- Tests pass.
- The health endpoint returns a successful response.
- Uptime Kuma has or can create a monitor for the health endpoint.
- SigNoz shows at least one trace from the service or job.
- Logs identify service, environment, owner, and runtime host.
- Project docs mention Ops Board and the service identity.
````

- [ ] **Step 2: Add final verification commands to the playground README**

Append this section to `examples/onboarding/README.md`:

````markdown
## Full Verification Checklist

Run:

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
docker compose -f examples/onboarding/compose.yaml config --quiet
docker compose -f examples/onboarding/compose.yaml build
docker compose --env-file .env -f compose.yaml up -d
docker compose -f examples/onboarding/compose.yaml up -d dummy-api
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:8000/work/demo -TimeoutSec 20
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

Expected:

- Tests pass.
- Compose config validates.
- Images build.
- Dummy API health and work endpoints respond.
- Dummy job exits successfully.
- SigNoz receives telemetry for `dummy-api` and `dummy-job`.
````

- [ ] **Step 3: Run all local tests**

Run:

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
```

Expected: all tests pass.

- [ ] **Step 4: Run Compose validation**

Run:

```powershell
docker compose --env-file .env -f compose.yaml config --quiet
docker compose -f examples/onboarding/compose.yaml config --quiet
```

Expected: both commands exit `0`.

- [ ] **Step 5: Build and run the playground**

Run:

```powershell
docker compose -f examples/onboarding/compose.yaml build
docker compose -f examples/onboarding/compose.yaml up -d dummy-api
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:8000/work/demo -TimeoutSec 20
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

Expected:

- Images build successfully.
- Dummy API returns successful JSON responses.
- Dummy job exits `0`.

- [ ] **Step 6: Capture local screenshots when the UI is available**

Use the Browser tool or Playwright from the repo root to capture local screenshots after the stack is running and any required UI login is complete.

Browser targets:

```text
http://localhost:3000
http://localhost:3001
http://localhost:8080
http://localhost:8000/health
http://localhost:8000/work/demo
```

Save captures to:

```text
docs/monitoring/images/homepage-overview.png
docs/monitoring/images/uptime-kuma-dashboard.png
docs/monitoring/images/signoz-services.png
docs/monitoring/images/signoz-traces.png
docs/onboarding/images/dummy-api-health.png
docs/onboarding/images/dummy-api-work.png
docs/onboarding/images/signoz-dummy-api-traces.png
docs/onboarding/images/signoz-dummy-job-traces.png
```

Expected: each saved image shows the named local UI or endpoint. If SigNoz or Uptime Kuma requires login, capture the relevant logged-in view after authentication.

- [ ] **Step 7: Add screenshot references after captures exist**

After images exist, add these references to `docs/monitoring/ops-board-user-manual.md`:

```markdown
![Homepage overview](images/homepage-overview.png)
![Uptime Kuma dashboard](images/uptime-kuma-dashboard.png)
![SigNoz services](images/signoz-services.png)
![SigNoz traces](images/signoz-traces.png)
```

Add these references to `docs/onboarding/human-guide.md`:

```markdown
![Dummy API health endpoint](images/dummy-api-health.png)
![Dummy API work endpoint](images/dummy-api-work.png)
![Dummy API traces in SigNoz](images/signoz-dummy-api-traces.png)
![Dummy job traces in SigNoz](images/signoz-dummy-job-traces.png)
```

- [ ] **Step 8: Verify docs and Git hygiene**

Run:

```powershell
Select-String -Path docs/onboarding/*.md,docs/monitoring/*.md,examples/onboarding/**/*.md -Pattern "UNRESOLVED|FIXME|\\?\\?"
git diff --check
git status --short --branch
```

Expected:

- `Select-String` prints no matches.
- `git diff --check` exits `0`.
- `git status --short --branch` shows only intentional files before commit.

- [ ] **Step 9: Commit Codex guide and final docs**

```powershell
git add docs/onboarding/codex-guide.md docs/onboarding/human-guide.md docs/monitoring/ops-board-user-manual.md docs/onboarding/images docs/monitoring/images examples/onboarding/README.md
git commit -m "docs: add codex onboarding guide"
```

---

## Final Verification

Run from the repo root after all tasks:

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
docker compose --env-file .env -f compose.yaml config --quiet
docker compose -f examples/onboarding/compose.yaml config --quiet
docker compose -f examples/onboarding/compose.yaml build
docker compose --env-file .env -f compose.yaml up -d
docker compose -f examples/onboarding/compose.yaml up -d dummy-api
Invoke-WebRequest -UseBasicParsing http://localhost:13133/ -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:8000/work/demo -TimeoutSec 20
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
git diff --check
```

Expected:

- All tests pass.
- Both Compose files validate.
- Example images build.
- Ops Board and the onboarding playground run.
- Collector health returns `200`.
- Dummy API returns successful responses.
- Dummy job exits successfully.
- SigNoz can show telemetry for `dummy-api` and `dummy-job`.
- No whitespace errors are reported.

---

## Rollback

Stop and remove only the onboarding playground:

```powershell
docker compose -f examples/onboarding/compose.yaml down --remove-orphans
```

Remove the committed playground and docs by reverting the task commits in reverse order:

```powershell
git revert <codex-guide-commit>
git revert <operator-human-docs-commit>
git revert <compose-runner-commit>
git revert <dummy-api-commit>
git revert <dummy-job-commit>
git revert <helper-commit>
git revert <contract-commit>
```

Ops Board itself is not removed by this rollback.

---

## Self-Review

- Spec coverage: The plan creates the onboarding contract, dummy job, dummy API, local helper, operator manual, human guide, Codex guide, and image folders required by the design spec.
- Runtime coverage: The plan validates local Python execution, Docker Compose execution, collector health, dummy API health, dummy API work spans, and dummy job spans.
- Tailscale coverage: The contract and manuals describe replacing `localhost` with the Ops Board Tailscale hostname for remote projects.
- Project standards: The plan uses Python 3.12, `uv`, `pytest`, `pydantic-settings`, `tenacity` for external/flaky I/O examples, and Docker BuildKit cache mounts.
- Unresolved marker scan: No unfinished task content is intentionally left for future design. Values such as `<ops-board-host>` and `<service-name>` appear only in the reusable Codex guide as inputs to be supplied by the target project.

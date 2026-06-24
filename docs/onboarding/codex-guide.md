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

For colleague projects running somewhere other than `hp-15`, use `http://hp-15:4318` as the normal OTLP endpoint. Use `localhost` only for code running directly on `hp-15` itself or for playground-local checks.

Keep project-owner work separate from Ops Board maintainer/admin work. In the target project, add package config, health endpoints, tests, and telemetry. Do not create or edit Uptime Kuma monitors, Homepage entries, Plane workspaces, or Ops Board-side credentials unless the user explicitly says this Codex session is acting as the Ops Board maintainer/admin.

Do not leave real onboardings on package defaults. Defaults exist for local tests only: `service_name=unknown-service`, `service_namespace=default`, `environment=local`, `owner=unknown`, `version=0.1.0`, `runtime_host=<OS hostname>`, `tailscale_host=None`, `otlp_endpoint=http://localhost:4318`, and `health_url=None`.

Use short stable environment labels such as `local`, `dev`, `test`, `staging`, or `prod`; the package accepts strings and does not enforce a closed enum. For `tailscale_host`, prefer the Tailscale MagicDNS name shown in the Tailscale app or Machines page. If the target host has no clear MagicDNS name, record the Tailscale IP in the health URL and leave `tailscale_host` unset.

Before editing app code, run this network preflight from the target runtime host:

```bash
curl -fsS --max-time 20 http://hp-15:13133/
```

If it fails, stop and report the reachability problem before installing the package or changing app code. This preflight proves the target host can reach the collector health endpoint; it does not prove telemetry export until a real request or job runs.

## Python App Changes

If the target is Python, add the package to the target Python project:

```bash
uv add "ops-board-observe @ git+https://github.com/Wenjun-Mao/ops-board.git#subdirectory=packages/ops-board-observe"
```

The package owns the OpenTelemetry, PyYAML, `pydantic-settings`, and `tenacity` dependencies needed by the helper. Do not add those transitive dependencies manually unless the target project already uses them directly.

If it is a FastAPI app, also ensure:

```bash
uv add fastapi uvicorn
```

Prefer `ops-board.yaml` for first onboarding unless the target already deploys through Docker, CI, or a process manager.

Create `ops-board.yaml` at the target project root:

```yaml
service:
  name: billing-api
  namespace: billing
  environment: prod
  owner: data-team
  version: 0.1.0

runtime:
  host: billing-host
  tailscale_host: billing-host.tailnet-name.ts.net

ops_board:
  otlp_endpoint: http://hp-15:4318
  health_url: http://billing-host.tailnet-name.ts.net:8000/health
```

The package reads `ops-board.yaml` automatically when the app starts from that directory. If the app starts from another working directory, set:

```bash
export OPS_BOARD_CONFIG_FILE=/absolute/path/to/ops-board.yaml
```

For Docker Compose, CI, or a process manager, use equivalent environment variables instead:

```dotenv
OPS_BOARD_SERVICE_NAME=billing-api
OPS_BOARD_SERVICE_NAMESPACE=billing
OPS_BOARD_ENVIRONMENT=prod
OPS_BOARD_OWNER=data-team
OPS_BOARD_VERSION=0.1.0
OPS_BOARD_RUNTIME_HOST=billing-host
OPS_BOARD_TAILSCALE_HOST=billing-host.tailnet-name.ts.net
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
OPS_BOARD_HEALTH_URL=http://billing-host.tailnet-name.ts.net:8000/health
```

Before editing app code, verify the package reads the intended service name. Run this from the target project root, after setting `OPS_BOARD_CONFIG_FILE`, or with the same `OPS_BOARD_*` environment variables used by Docker, CI, or the process manager:

```bash
uv run python -c "from ops_board_observe import load_settings; print(load_settings().service_name)"
```

Expected for the example above:

```text
billing-api
```

## Script Or Scheduled Job Pattern

Add bootstrap once near the entrypoint:

```python
from ops_board_observe import bootstrap_observability, observe

bootstrap_observability()
```

Decorate the main work:

```python
@observe("<service-name>.run")
def run_job() -> dict[str, str]:
    return {"status": "success"}
```

Network requests or external I/O must use `tenacity` retries:

If the target project imports `tenacity` directly for this retry snippet, add it as a direct dependency even though `ops-board-observe` owns its own helper dependencies:

```bash
uv add tenacity
```

```python
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(wait=wait_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(3))
def call_external_service() -> str:
    return "ok"
```

## Web/API Pattern

Bootstrap observability once during app startup. For FastAPI, prefer the lifespan pattern:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from ops_board_observe import bootstrap_observability, observe


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    bootstrap_observability()
    yield


app = FastAPI(lifespan=lifespan)
```

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
    return {"status": "processed"}
```

## Docker Compose Pattern

Add these environment variables to the service:

```yaml
environment:
  OPS_BOARD_SERVICE_NAME: <service-name>
  OPS_BOARD_SERVICE_NAMESPACE: <namespace>
  OPS_BOARD_ENVIRONMENT: <environment>
  OPS_BOARD_OWNER: <owner>
  OPS_BOARD_VERSION: 0.1.0
  OPS_BOARD_RUNTIME_HOST: <host>
  OPS_BOARD_TAILSCALE_HOST: <tailscale-host>
  OPS_BOARD_OTLP_ENDPOINT: http://hp-15:4318
  OPS_BOARD_HEALTH_URL: http://<service-tailscale-host>:<port>/health
```

## Validation Commands

If using `ops-board.yaml` and validation runs outside the directory containing it, export the config path first:

```bash
export OPS_BOARD_CONFIG_FILE=/absolute/path/to/ops-board.yaml
```

For Docker Compose, CI, or process-manager deployments, validate with the intended `OPS_BOARD_*` environment instead.

Run project tests:

```bash
uv run pytest -v
```

Add or adjust tests for package-flow onboarding changes. Unit tests should exercise observability setup with telemetry export disabled or with the exporter mocked; ordinary unit tests must not depend on live OTLP, SigNoz, or network reachability.

Verify health endpoint:

```bash
curl -fsS --max-time 20 <health-url>
```

Record or report the health URL for the Ops Board maintainer/admin.

> [!NOTE]
> **Ops Board maintainer/admin step**
> The maintainer/admin creates or confirms the Uptime Kuma HTTP monitor and any Homepage link. The target project only needs a reachable health URL and working telemetry.

Verify Ops Board collector from the target host:

```bash
curl -fsS --max-time 20 http://hp-15:13133/
```

This should be the same preflight from the start of the guide, re-run after deployment or environment changes.

Run one request or one job execution, then check SigNoz for:

```text
service.name = <service-name>
deployment.environment = <environment>
```

## Acceptance Criteria

The target project is onboarded when:

- Tests pass.
- The target runtime host can reach `http://hp-15:13133/`.
- The health endpoint returns a successful response.
- The health URL is recorded for the Ops Board maintainer/admin.
- The Ops Board maintainer/admin has enough information to create or confirm the Uptime Kuma monitor.
- SigNoz shows at least one trace from the service or job.
- Logs identify service, environment, owner, and runtime host.
- Project docs mention Ops Board and the service identity.

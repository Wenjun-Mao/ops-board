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

Add config through env vars:

```dotenv
OPS_BOARD_SERVICE_NAME=<service-name>
OPS_BOARD_SERVICE_NAMESPACE=<namespace>
OPS_BOARD_ENVIRONMENT=<environment>
OPS_BOARD_OWNER=<owner>
OPS_BOARD_RUNTIME_HOST=<host>
OPS_BOARD_TAILSCALE_HOST=<tailscale-host>
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
OPS_BOARD_HEALTH_URL=http://<service-tailscale-host>:<port>/health
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
  OPS_BOARD_RUNTIME_HOST: <host>
  OPS_BOARD_TAILSCALE_HOST: <tailscale-host>
  OPS_BOARD_OTLP_ENDPOINT: http://hp-15:4318
  OPS_BOARD_HEALTH_URL: http://<service-tailscale-host>:<port>/health
```

## Validation Commands

Run project tests:

```bash
uv run pytest -v
```

Verify health endpoint:

```bash
curl -fsS --max-time 20 <health-url>
```

Verify Ops Board collector from the target host:

```bash
curl -fsS --max-time 20 http://hp-15:13133/
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

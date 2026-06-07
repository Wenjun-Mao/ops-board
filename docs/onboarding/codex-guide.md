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

Use `http://<ops-board-tailscale-hostname>:4318` for remote machines connected through Tailscale. For the HP-15 deployment, use `http://hp-15:4318`.

## Python App Changes

If the target is Python, add dependencies using `uv`:

```bash
uv add pydantic-settings pyyaml opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http tenacity
```

If it is a FastAPI app, also ensure:

```bash
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
def run_job() -> dict[str, str]:
    return {"status": "success"}
```

Network requests or external I/O must use `tenacity` retries:

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
  OPS_BOARD_OTLP_ENDPOINT: http://<ops-board-host>:4318
  OPS_BOARD_HEALTH_URL: http://<service-host>:<port>/health
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
curl -fsS --max-time 20 http://<ops-board-host>:13133/
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

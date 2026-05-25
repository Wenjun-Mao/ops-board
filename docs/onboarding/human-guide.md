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
def run_job() -> dict[str, str]:
    return {"status": "success"}
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
    return {"item_id": item_id, "status": "processed"}
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

Then open:

```text
http://localhost:18080/health
http://localhost:18080/work/demo
```

Expected local responses:

![Dummy API health response](images/dummy-api-health.png)

![Dummy API work response](images/dummy-api-work.png)

Open SigNoz and look for:

```text
dummy-api
dummy-job
```

On a clean rebuild, SigNoz may ask you to create the first admin account before you can inspect traces. The playground still emits telemetry while you finish that setup.

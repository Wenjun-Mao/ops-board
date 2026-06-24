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
- Long-running services expose a health endpoint and share the URL with the Ops Board maintainer/admin.
- Python jobs or key functions can emit observed spans.
- SigNoz can show useful traces or logs.

## Before You Start

This guide assumes the project you are onboarding runs somewhere other than `hp-15`. For colleague projects, use this default OTLP endpoint:

```text
http://hp-15:4318
```

Use `http://localhost:4318` only for code running directly on `hp-15` itself.

Before installing the package or editing code, run this from the machine where the project will run:

```bash
curl -fsS --max-time 20 http://hp-15:13133/
```

Expected: the command exits successfully. If it fails, fix Tailscale, DNS, firewall, or collector reachability with the Ops Board maintainer/admin before continuing. This only proves the collector health endpoint is reachable; the first success test later proves the project emits telemetry.

Collect:

```text
service.name
service.namespace
deployment.environment
owner
runtime host
Tailscale hostname or IP
health endpoint URL, if this is a service
Ops Board OTLP endpoint
```

## Config Fields

The package has local-test defaults, but a real onboarding should fill in the fields below so SigNoz, Uptime Kuma, and teammates can identify the project. The package accepts strings for these values; the "Use" column names the convention Ops Board expects.

| YAML field | Required for onboarding? | Package default | Use |
|------------|---------------------------|-----------------|-----|
| `service.name` | Yes | `unknown-service` | Stable service name in SigNoz, such as `billing-api` or `invoice-job`. Use lowercase words with `-` when possible. |
| `service.namespace` | Yes | `default` | Project, product, repo family, or team grouping, such as `billing` or `content-shuttle`. |
| `service.environment` | Yes | `local` | Runtime environment. Use a short stable label such as `local`, `dev`, `test`, `staging`, or `prod`. `test` is fine for a real test environment. |
| `service.owner` | Yes | `unknown` | Person or team responsible for first response, such as `mk`, `ops`, or `data-team`. |
| `service.version` | Recommended | `0.1.0` | App release, package version, commit tag, or a simple placeholder during first onboarding. |
| `runtime.host` | Yes | the OS hostname from Python | Machine or VPS where the project runs, such as `hp-15`, `billing-vps-1`, or `john-laptop`. |
| `runtime.tailscale_host` | Recommended when the host is on Tailscale | empty | Tailscale MagicDNS name or Tailscale IP for the project host. This helps people find the runtime host and helps maintainers build health-check URLs. |
| `ops_board.otlp_endpoint` | Yes for projects not running directly on `hp-15` | `http://localhost:4318` | Where traces and logs are sent. For colleague projects, use `http://hp-15:4318`. |
| `ops_board.health_url` | Services only | empty | HTTP health endpoint the Ops Board maintainer/admin can monitor, such as `http://api-host.tailnet-name.ts.net:8000/health`. Omit for one-shot jobs with no health endpoint. |

These values become OpenTelemetry resource attributes in SigNoz:

```text
service.name
service.namespace
service.version
deployment.environment
service.owner
host.name
ops_board.tailscale_host
```

`ops_board.health_url` is not sent as a trace attribute by the package. It is handoff information for Uptime Kuma monitor setup.

To find `runtime.tailscale_host`, use whichever source is easiest:

1. Open the Tailscale app or admin console and find the machine name for the project host.
2. If MagicDNS is enabled, use the machine name, for example `billing-host`, when short names resolve from your tailnet.
3. For a more explicit value, use the full MagicDNS name shown on the machine page, for example `billing-host.tailnet-name.ts.net`.
4. If DNS names are confusing but the host is reachable, use the Tailscale IP in the health URL and leave `runtime.tailscale_host` empty.

From the project host, verify the chosen name or IP before sharing it:

```bash
curl -fsS --max-time 20 http://api-host.tailnet-name.ts.net:8000/health
```

## Python Package Setup

Do these steps from your project's root folder.

### Step 1: Install The Package

```bash
uv add "ops-board-observe @ git+https://github.com/Wenjun-Mao/ops-board.git#subdirectory=packages/ops-board-observe"
```

### Step 2: Create `ops-board.yaml`

Create this file at your project root:

```text
ops-board.yaml
```

For a script, scheduled job, or worker, start with this exact file and edit the names:

```yaml
service:
  name: my-job
  namespace: my-project
  environment: prod
  owner: team-name
  version: 0.1.0

runtime:
  host: job-host
  tailscale_host: job-host.tailnet-name.ts.net

ops_board:
  otlp_endpoint: http://hp-15:4318
```

For a web/API service with a health endpoint, use the same file and add `health_url`:

```yaml
service:
  name: my-api
  namespace: my-project
  environment: prod
  owner: team-name
  version: 0.1.0

runtime:
  host: api-host
  tailscale_host: api-host.tailnet-name.ts.net

ops_board:
  otlp_endpoint: http://hp-15:4318
  health_url: http://api-host.tailnet-name.ts.net:8000/health
```

The package automatically reads `ops-board.yaml` when you run Python from the folder that contains it.

If you run Python from a different folder, point to the file explicitly:

```bash
export OPS_BOARD_CONFIG_FILE=/absolute/path/to/ops-board.yaml
```

### Step 3: Check The Config Loads

Run this from the same folder where you will start the app or job:

```bash
uv run python -c "from ops_board_observe import load_settings; print(load_settings().service_name)"
```

Expected for the job example:

```text
my-job
```

Expected for the API example:

```text
my-api
```

### Step 4: Import The Package

```python
from ops_board_observe import bootstrap_observability, observe
```

## Python Script Or Scheduled Job

After `ops-board.yaml` exists and the sanity check prints `my-job`, add observability near the job entrypoint.

```python
from ops_board_observe import bootstrap_observability, observe

bootstrap_observability()


@observe("my-job.run")
def run_job() -> dict[str, str]:
    return {"status": "success"}
```

Run the job, then check SigNoz for `service.name = my-job`.

## Python Web/API Service

For the API example below, use the API `ops-board.yaml` example from Step 2 and confirm the sanity check prints `my-api`.

Bootstrap observability once during application startup. For FastAPI, use lifespan:

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
    return {"status": "ok", "service": "my-api"}
```

Confirm the health endpoint returns a successful response from a tailnet machine:

```bash
curl -fsS --max-time 20 http://api-host.tailnet-name.ts.net:8000/health
```

Wrap key handlers or functions:

```python
@observe("my-api.process-request")
def process_request(item_id: str) -> dict[str, str]:
    return {"item_id": item_id, "status": "processed"}
```

After this check succeeds, share the health URL with the Ops Board maintainer/admin.

> [!NOTE]
> **Ops Board maintainer/admin step**
> The colleague onboarding the project only needs to provide the health URL and confirm it returns a successful response. The Ops Board maintainer/admin creates or confirms the Uptime Kuma HTTP monitor from `http://hp-15:3001`; the maintainer workflow lives in `docs/monitoring/ops-board-user-manual.md`.

## Dockerized App Or CI

For Docker Compose, CI, or a process manager, environment variables are usually easier than mounting `ops-board.yaml`.

Use the same values as the YAML examples:

For a job, omit `OPS_BOARD_HEALTH_URL` when there is no health endpoint:

```yaml
environment:
  OPS_BOARD_SERVICE_NAME: my-job
  OPS_BOARD_SERVICE_NAMESPACE: my-project
  OPS_BOARD_ENVIRONMENT: prod
  OPS_BOARD_OWNER: team-name
  OPS_BOARD_VERSION: 0.1.0
  OPS_BOARD_RUNTIME_HOST: job-host
  OPS_BOARD_TAILSCALE_HOST: job-host.tailnet-name.ts.net
  OPS_BOARD_OTLP_ENDPOINT: http://hp-15:4318
```

For a web/API service with a health endpoint:

```yaml
environment:
  OPS_BOARD_SERVICE_NAME: my-api
  OPS_BOARD_SERVICE_NAMESPACE: my-project
  OPS_BOARD_ENVIRONMENT: prod
  OPS_BOARD_OWNER: team-name
  OPS_BOARD_VERSION: 0.1.0
  OPS_BOARD_RUNTIME_HOST: api-host
  OPS_BOARD_TAILSCALE_HOST: api-host.tailnet-name.ts.net
  OPS_BOARD_OTLP_ENDPOINT: http://hp-15:4318
  OPS_BOARD_HEALTH_URL: http://api-host.tailnet-name.ts.net:8000/health
```

Use Docker logs plus SigNoz traces as the first debugging layer.

## Removing Ops Board Later

If the project stops reporting to Ops Board, remove the integration deliberately:

1. Remove `ops_board_observe` imports, `bootstrap_observability()`, and `@observe(...)` decorators.
2. Remove `OPS_BOARD_*` environment variables, config file entries, and Docker secrets.
3. Remove the package:

```bash
uv remove ops-board-observe
```

4. Tell the Ops Board maintainer/admin whether the Uptime Kuma monitor, Homepage link, or Ops Board-side references should be removed or updated.
5. Run the project tests and a normal local start command.

## Remote Tailscale Machine

1. Join the same tailnet as `hp-15`.
2. From the project host, re-run the collector preflight after deployment changes:

   ```bash
   curl -fsS --max-time 20 http://hp-15:13133/
   ```

3. Confirm `ops-board.yaml` uses `otlp_endpoint: http://hp-15:4318`, or confirm the process has `OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318`.
4. Run the app or job.
5. Check SigNoz from `http://hp-15:8080`.

Health checks can point either from Uptime Kuma to the remote service's tailnet URL, or from the service host back to Ops Board if the service cannot accept inbound checks.

> [!NOTE]
> **Ops Board maintainer/admin step**
> The maintainer/admin chooses the monitor direction and Uptime Kuma settings. The colleague provides the reachable health URL, or explains why inbound tailnet checks are not possible.

## First Success Test

After onboarding, prove the project-owner checks:

```text
The project host can reach http://hp-15:13133/.
The health endpoint returns a successful response.
SigNoz can see at least one trace from the project.
The project docs say who owns the project.
The project docs say where the project runs.
```

> [!NOTE]
> **Ops Board maintainer/admin step**
> The Ops Board maintainer/admin confirms Uptime Kuma can monitor the health endpoint and that Ops Board-side links or references are in the right place.

## Example Playground

Use the local playground before onboarding a real project:

```bash
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

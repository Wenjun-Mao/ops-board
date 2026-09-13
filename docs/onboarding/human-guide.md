# Onboard A Project To Ops Board

This guide is for a project owner or colleague. Start with the smallest useful outcome: a health check visible to the Ops Board maintainer. You do not need to install a package or change code when your API already has a suitable health endpoint.

Ops Board dashboards remain private on Tailscale. A public HTTPS health URL lets Uptime Kuma make an outbound check; it does not make Ops Board public.

## Start Here: Existing Health Endpoint

Use this path for a long-running API or service that already returns a simple successful health response.

1. Check the endpoint from a machine that should be able to reach it:

   ```bash
   curl -fsS --max-time 20 <health-url>
   ```

2. Send the Ops Board maintainer/admin:
   - a display name, such as `Billing API`;
   - the exact health URL, including `http://` or `https://`;
   - whether it is reachable over Tailscale/private networking or public HTTPS;
   - any expected success result other than HTTP `2xx`.

3. The maintainer validates the URL from the Uptime Kuma container, adds it to the Git-managed registry, runs bootstrap, and confirms it shows **Up** in the private Uptime Kuma dashboard.

This is a complete first-tier onboarding result. You do not need an `ops-board.yaml`, an OTLP endpoint, or source-code changes for this health-only path.

> [!NOTE]
> **Ops Board maintainer/admin step**
> Project monitor configuration belongs in the Ops Board repository, not in the target project. See `stacks/uptime-kuma/docs/monitors.md` and `docs/monitoring/ops-board-user-manual.md`.

## Which URL To Share

Use the URL Uptime Kuma can reach from the Ops Board host:

| Target location | Example | Notes |
|-----------------|---------|-------|
| Tailscale/private service | `http://api-host.tailnet-name.ts.net:8000/health` | Use a MagicDNS name or Tailscale IP when the service is on the tailnet. |
| Public service | `https://api.example.com/health` | Keep normal TLS verification enabled. This does not expose Ops Board. |

The first registry supports anonymous HTTP `GET` checks. Do not send health endpoint credentials in chat or add them to a tracked file. Tell the maintainer when authentication is required; that needs a separate secrets-backed monitor design.

## Optional: Deeper Telemetry

Add the `ops-board-observe` package only when traces and logs would make the project easier to debug, or when you need execution evidence for a job. It is optional after health monitoring and is not required for a service to appear in Uptime Kuma.

For a project running somewhere other than `hp-15`, the normal OTLP endpoint is:

```text
http://hp-15:4318
```

Use `http://localhost:4318` only when the project itself runs directly on `hp-15`.

Before installing the package or changing code, run this from the project runtime host:

```bash
curl -fsS --max-time 20 http://hp-15:13133/
```

This proves the host can reach the collector health endpoint. It does not prove telemetry is exporting; run an app request or job after instrumentation and check SigNoz.

### Package Configuration

Install the package from the project root:

```bash
uv add "ops-board-observe @ git+https://github.com/Wenjun-Mao/ops-board.git#subdirectory=packages/ops-board-observe"
```

Create `ops-board.yaml` with the service identity used by SigNoz:

```yaml
service:
  name: my-service
  namespace: my-project
  environment: prod
  owner: team-name
  version: 0.1.0

runtime:
  host: service-host
  tailscale_host: service-host.tailnet-name.ts.net

ops_board:
  otlp_endpoint: http://hp-15:4318
```

The health URL stays in the Ops Board monitor registry, not in this package configuration.

| Field | Required for telemetry | Default | How to choose it |
|-------|------------------------|---------|------------------|
| `service.name` | Yes | `unknown-service` | A stable service label, for example `billing-api` or `invoice-job`. |
| `service.namespace` | Yes | `default` | Project, product, repo family, or team grouping. |
| `service.environment` | Yes | `local` | A short label such as `local`, `dev`, `test`, `staging`, or `prod`. |
| `service.owner` | Yes | `unknown` | The person or team responsible for first response. |
| `service.version` | Recommended | `0.1.0` | A release, tag, commit label, or temporary first-onboarding value. |
| `runtime.host` | Yes | Python OS hostname | The actual machine or VPS name. |
| `runtime.tailscale_host` | Recommended on Tailscale | empty | The MagicDNS name shown in Tailscale, or leave empty when unavailable. |
| `ops_board.otlp_endpoint` | Yes off-host | `http://localhost:4318` | Use `http://hp-15:4318` from another tailnet host. |

Find the Tailscale host in the Tailscale app or Machines page. A full name can look like `service-host.tailnet-name.ts.net`; when MagicDNS is unclear, leave this field empty rather than guessing.

Confirm the package reads the expected identity:

```bash
uv run python -c "from ops_board_observe import load_settings; print(load_settings().service_name)"
```

### Python Job

Add bootstrap once near the job entrypoint and observe the main work:

```python
from ops_board_observe import bootstrap_observability, observe

bootstrap_observability()


@observe("my-job.run")
def run_job() -> dict[str, str]:
    return {"status": "success"}
```

For a one-shot cron job with no health endpoint, this optional telemetry is the current way to establish that a run happened. A health monitor alone cannot prove job success.

### Python Web/API Service

For FastAPI, bootstrap once in the lifespan and observe important work:

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


@observe("my-service.process")
def process() -> dict[str, str]:
    return {"status": "processed"}
```

If this service needs a new `/health` endpoint, add and test it as normal application work, then return to the agentless health-monitoring path above.

### Docker, CI, Or Process Managers

Use the same telemetry identity through environment variables when a YAML file is inconvenient:

```dotenv
OPS_BOARD_SERVICE_NAME=my-service
OPS_BOARD_SERVICE_NAMESPACE=my-project
OPS_BOARD_ENVIRONMENT=prod
OPS_BOARD_OWNER=team-name
OPS_BOARD_VERSION=0.1.0
OPS_BOARD_RUNTIME_HOST=service-host
OPS_BOARD_TAILSCALE_HOST=service-host.tailnet-name.ts.net
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
```

## Verify And Remove

For health-only onboarding, the maintainer confirms the Uptime Kuma monitor is Up. For telemetry onboarding, also run a request or job and check SigNoz for the configured `service.name` and `deployment.environment`.

To remove optional telemetry later:

1. Remove `ops_board_observe` imports, bootstrap calls, and decorators.
2. Remove the `OPS_BOARD_*` values or `ops-board.yaml` fields used only for telemetry.
3. Run `uv remove ops-board-observe` and the project’s normal tests.
4. Tell the Ops Board maintainer to pause, archive, or delete the health monitor. Removing a Git registry entry intentionally does not delete its Uptime Kuma history.

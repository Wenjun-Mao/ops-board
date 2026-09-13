# Codex Guide: Onboard A Project To Ops Board

Use this guide when a Codex session is helping a separate project join Ops Board. Classify the request before editing application code.

## Default: Agentless Health Monitoring

When the target already has an anonymous HTTP health endpoint, do not install `ops-board-observe` or change the project. Gather:

```text
display name
exact health URL, including http:// or https://
private/Tailscale or public HTTPS reachability
expected successful HTTP status range
```

The target owner verifies the endpoint from a relevant reachable machine. The Ops Board maintainer/admin then validates it from the Uptime Kuma container, registers it in `stacks/uptime-kuma/bootstrap/monitors.yaml`, runs `./scripts/bootstrap-uptime-kuma.sh`, and verifies it is Up in the private Uptime Kuma dashboard.

Do not create or edit a Uptime Kuma monitor from a target-project session unless the user explicitly says that session is acting as the Ops Board maintainer/admin. Do not expose Ops Board dashboards because a target health URL is public.

For agentless registration, use a stable lowercase kebab-case `id` and a human-friendly `name`:

```yaml
project_monitors:
  - id: billing-api
    name: Billing API
    url: https://api.example.com/health
    accepted_statuscodes: ["200-299"]
```

The registry owns its marked monitor's name, URL, enabled state, expected statuses, interval/retry/redirect settings, and TLS-verification setting. It does not delete removed entries or take over a same-named manual monitor. Project monitors must remain out of the `ops-board` status page and Homepage widget.

## Optional: Telemetry And Execution Evidence

Use this tier only when traces/logs are useful or when a one-shot job needs execution evidence. A cron job with no health endpoint cannot be meaningfully proven healthy by the agentless HTTP path alone.

Before editing code, run this from the target runtime host when it is not `hp-15`:

```bash
curl -fsS --max-time 20 http://hp-15:13133/
```

If it fails, report the network issue before installing a dependency or changing application code. `localhost` means the target's own host; use `http://hp-15:4318` for OTLP from another tailnet machine.

### Python Integration

Add the single package dependency from the target project root:

```bash
uv add "ops-board-observe @ git+https://github.com/Wenjun-Mao/ops-board.git#subdirectory=packages/ops-board-observe"
```

Do not add its transitive OpenTelemetry, YAML, settings, or retry dependencies directly unless the target already uses one itself.

Create `ops-board.yaml` or provide equivalent `OPS_BOARD_*` deployment values. The health URL is not package configuration; the Git registry is the monitor source of truth.

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
```

Real telemetry onboarding replaces package defaults with a stable service identity. Use short labels such as `local`, `dev`, `test`, `staging`, or `prod`; `environment` is a convention, not a closed enum. Find `tailscale_host` in the Tailscale app or Machines page. Leave it unset if no reliable MagicDNS name exists.

Validate from the same directory and environment used to start the target:

```bash
uv run python -c "from ops_board_observe import load_settings; print(load_settings().service_name)"
```

For a job:

```python
from ops_board_observe import bootstrap_observability, observe

bootstrap_observability()


@observe("billing-job.run")
def run_job() -> dict[str, str]:
    return {"status": "success"}
```

For a FastAPI service, bootstrap once in lifespan and observe important work:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from ops_board_observe import bootstrap_observability


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    bootstrap_observability()
    yield


app = FastAPI(lifespan=lifespan)
```

For Docker Compose, CI, or a process manager, use the equivalent environment variables:

```dotenv
OPS_BOARD_SERVICE_NAME=billing-api
OPS_BOARD_SERVICE_NAMESPACE=billing
OPS_BOARD_ENVIRONMENT=prod
OPS_BOARD_OWNER=data-team
OPS_BOARD_VERSION=0.1.0
OPS_BOARD_RUNTIME_HOST=billing-host
OPS_BOARD_TAILSCALE_HOST=billing-host.tailnet-name.ts.net
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
```

## Validation And Handoff

For health-only onboarding, acceptance is:

- The endpoint responds successfully from Uptime Kuma.
- The registered project monitor is Up exactly once.
- The core `ops-board` status page remains limited to Ops Board monitors.

For optional telemetry, additionally:

- Run project tests without requiring a live OTLP endpoint in ordinary unit tests.
- Run one request or job with the intended config.
- Confirm SigNoz has the expected `service.name` and `deployment.environment`.
- Confirm logs or spans identify the expected owner and runtime host.

When removing telemetry, remove imports, bootstrap/decorator calls, its configuration, and the package with `uv remove ops-board-observe`. Ask the Ops Board maintainer to retire the monitor explicitly; deleting a registry entry intentionally preserves its monitor history.

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

For the HP-15 deployment, remote tailnet clients should use `http://hp-15:4318` for OTLP HTTP and `http://hp-15:8080` for the SigNoz UI.

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

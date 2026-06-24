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

For the HP-15 deployment, colleague projects and other tailnet machines should use:

```text
OTLP HTTP:         http://hp-15:4318
SigNoz UI:         http://hp-15:8080
Uptime Kuma:       http://hp-15:3001
Homepage:          http://hp-15:3000
Plane:             http://hp-15:8082
```

For local testing from a shell or browser running directly on `hp-15`, or for playground-local checks on that host, use:

```text
OTLP HTTP (only for code running directly on hp-15 or playground-local checks): http://localhost:4318
OTLP gRPC (only for code running directly on hp-15 or playground-local checks): http://localhost:4317
Collector health:                                                        http://localhost:13133
SigNoz UI:                                                               http://localhost:8080
Uptime Kuma:                                                             http://localhost:3001
Homepage:                                                                http://localhost:3000
Plane:                                                                   http://localhost:8082
```

For non-HP-15 deployments, replace `hp-15` with the Ops Board host's Tailscale MagicDNS name or Tailscale IP.

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
  otlp_endpoint: http://hp-15:4318
  health_url: http://<service-tailscale-host>:8000/health
```

## Python Config Channels

Use one config channel first. Do not duplicate the same field in multiple places unless you are intentionally overriding it.

| Channel | Use when | How `ops-board-observe` finds it |
|---------|----------|-----------------------------------|
| `ops-board.yaml` | First onboarding, local project runs, scripts, scheduled jobs | Automatically from the current working directory, or through `OPS_BOARD_CONFIG_FILE` |
| `OPS_BOARD_*` environment variables | Docker Compose, CI, systemd, process managers | The process environment |
| Docker secret files | Deployed values that should not appear in env or tracked files | `OPS_BOARD_SECRETS_DIR`, or `/run/secrets` by default |

For a teammate onboarding a Python project by hand, `ops-board.yaml` is the default path. Environment variables are the deployment override path.

## Python Environment Variable Conventions

The v1 Python integration contract is the `ops-board-observe` package. Projects install it as one dependency and import `ops_board_observe`. They should not copy helper files from the playground.

When a project uses environment variables instead of `ops-board.yaml`, it uses the `OPS_BOARD_` prefix:

```dotenv
OPS_BOARD_SERVICE_NAME=example-api
OPS_BOARD_SERVICE_NAMESPACE=ops-board.examples
OPS_BOARD_ENVIRONMENT=local
OPS_BOARD_OWNER=mk
OPS_BOARD_VERSION=0.1.0
OPS_BOARD_RUNTIME_HOST=example-host
OPS_BOARD_TAILSCALE_HOST=example-host.tailnet-name.ts.net
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
OPS_BOARD_HEALTH_URL=http://<service-tailscale-host>:8000/health
```

`OPS_BOARD_CONFIG_FILE` selects a YAML file when Python does not start from that directory. `OPS_BOARD_SECRETS_DIR` selects the Docker secret-file directory when using secret files.

Uptime Kuma monitor URLs are handled in monitor setup docs, not package config.

The package also sets standard OpenTelemetry resource attributes in process. Projects may still use standard `OTEL_*` variables when they outgrow the package.

## Python Package Config Precedence

The v1 package loads config in this order:

1. Explicit function arguments
2. Docker secret files from `OPS_BOARD_SECRETS_DIR` or `/run/secrets`
3. `OPS_BOARD_*` environment variables
4. YAML config file
5. Defaults

Example: if `ops-board.yaml` says `service.name: billing-api` but the process environment has `OPS_BOARD_SERVICE_NAME=billing-api-worker`, the package uses `billing-api-worker`.

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

## Evidence Checklist

After onboarding, capture or link concise evidence for:

- Config evidence: service identity, runtime host, Tailscale host, OTLP endpoint, and health URL are present in env, secrets, compose, or project docs.
- App/job run evidence: at least one successful app request or job run completed with the onboarded config.
- SigNoz evidence: traces and logs identify the expected service name, environment, owner, and runtime host.
- Health monitor evidence: when a health endpoint exists, Uptime Kuma or the chosen monitor can reach it successfully.

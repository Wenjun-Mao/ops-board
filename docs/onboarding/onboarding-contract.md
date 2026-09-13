# Ops Board Onboarding Contract

Ops Board is a private operating center for services and jobs that run across local computers, VPSs, and cloud providers. Tailscale is the dashboard access boundary for v1. A public target health URL does not change that boundary.

Project onboarding has two independent tiers. Complete the first tier whenever an existing API has a suitable health endpoint; add the second only when richer operational evidence is worth a project change.

## Tier 1: Agentless Health Monitoring

The target project makes no package, dependency, or code change. The project owner supplies a reachable anonymous HTTP health URL; the Ops Board maintainer/admin owns its Uptime Kuma registry entry.

The Git-backed registry is `stacks/uptime-kuma/bootstrap/monitors.yaml`:

```yaml
project_monitors:
  - id: billing-api
    name: Billing API
    url: https://api.example.com/health
    accepted_statuscodes: ["200-299"]
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | Stable, unique lowercase kebab-case key. It is the reconciliation identity, not a display label. |
| `name` | Yes | Human-friendly Uptime Kuma label. It may change without replacing the monitor. |
| `url` | Yes | Anonymous `http://` or `https://` endpoint reachable from the Uptime Kuma container. |
| `accepted_statuscodes` | No | Defaults to `["200-299"]`. |
| `enabled` | No | Defaults to `true`; use `false` to retain but pause a check. |
| HTTP timing/TLS fields | No | Code-backed defaults are documented in `stacks/uptime-kuma/docs/monitors.md`. |

The bootstrap creates and updates only monitors marked with the registry ID. It never deletes a removed entry and never adopts a same-named manual monitor. Project monitors are private dashboard entries, not members of the core `ops-board` status page or Homepage widget.

### URL Reachability

| Target type | Example | Rule |
|-------------|---------|------|
| Private tailnet service | `http://api-host.tailnet-name.ts.net:8000/health` | Use a MagicDNS name or Tailscale IP that the Ops Board host can route to. |
| Public service | `https://api.example.com/health` | Uptime Kuma makes an outbound HTTPS check while Ops Board remains private. |

TLS verification is on by default. Authenticated health endpoints, request headers, and notification providers are not part of the first-tier registry. Their secrets must never be committed.

## Tier 2: Optional Telemetry

`ops-board-observe` is the Python integration contract for traces, logs, and execution-level evidence. It is optional for services already covered by Tier 1, and it is the current useful path for a one-shot job that has no health endpoint.

When a project opts in, it defines a stable telemetry identity:

| Field | Required | Example | Notes |
|-------|----------|---------|-------|
| `service.name` | Yes | `billing-api` | Stable service label in SigNoz. |
| `service.namespace` | Yes | `billing` | Project, repo family, product, or team group. |
| `deployment.environment` | Yes | `prod` | Use a short label such as `local`, `dev`, `test`, `staging`, or `prod`. |
| `owner` | Yes | `data-team` | Person or team responsible for first response. |
| `runtime.host` | Yes | `billing-vps-1` | Actual runtime hostname or VPS name. |
| `tailscale.host` | Recommended | `billing-host.tailnet-name.ts.net` | MagicDNS name when it exists. |
| `runtime.provider` | Optional | `aws` | Useful in multi-provider environments. |
| `runtime.country` | Optional | `CA` | Useful for latency and data-location context. |

The package's local-test defaults are not sufficient for real telemetry onboarding: `service_name=unknown-service`, `service_namespace=default`, `environment=local`, `owner=unknown`, `version=0.1.0`, `runtime_host=<OS hostname>`, `tailscale_host=None`, and `otlp_endpoint=http://localhost:4318`.

`health_url` remains accepted package compatibility metadata but is not a source for monitor provisioning. The registry above is authoritative.

### Package Configuration

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
```

Projects can instead use `OPS_BOARD_*` environment variables or Docker secret files. Configuration precedence remains: explicit function arguments, secret files, environment variables, YAML, then defaults. See ADR 005 for package runtime semantics.

## Ownership

| Role | Owns |
|------|------|
| Project owner or colleague | Existing health endpoint availability, endpoint details, optional app/package changes, telemetry identity, and project docs. |
| Ops Board maintainer/admin | Registry changes, Uptime Kuma bootstrap and lifecycle, dashboard placement, Ops Board credentials, and SigNoz/Plane first-run setup. |

When one person does both roles, preserve the distinction in docs and handoffs. A target-project Codex session must not edit Ops Board monitor state unless it is explicitly acting as the maintainer/admin.

## HP-15 Endpoint Conventions

For projects running elsewhere on the tailnet:

```text
OTLP HTTP:         http://hp-15:4318
SigNoz UI:         http://hp-15:8080
Uptime Kuma:       http://hp-15:3001
Homepage:          http://hp-15:3000
Plane:             http://hp-15:8082
Collector health:  http://hp-15:13133
```

Use `localhost` only from code, a shell, or a browser running directly on HP-15. For a different Ops Board host, replace `hp-15` with that host's Tailscale MagicDNS name or Tailscale IP.

Before a telemetry integration changes app code, its runtime host should pass:

```bash
curl -fsS --max-time 20 http://hp-15:13133/
```

This is a collector reachability preflight, not proof of successful export.

## Acceptance And Evidence

Tier 1 is complete when:

- The maintainer validates the endpoint from Uptime Kuma.
- The Git-managed project monitor appears once and reports Up.
- The core `ops-board` status page remains limited to Ops Board baseline monitors.

Tier 2 adds:

- A real request or job run with the intended configuration.
- SigNoz evidence for the expected service name and environment.
- Traces or logs that identify the expected owner and runtime host.

For scheduled jobs without a health endpoint, do not claim Tier 1 confirms successful execution. Use Tier 2 evidence until a dedicated job heartbeat/push contract is designed.

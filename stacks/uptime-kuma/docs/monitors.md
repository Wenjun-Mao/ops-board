# Uptime Kuma Monitors

Uptime Kuma is Ops Board's v1 source for endpoint health. The Git-backed monitor registry is `stacks/uptime-kuma/bootstrap/monitors.yaml`.

Run the bootstrap after Uptime Kuma is running:

```bash
./scripts/bootstrap-uptime-kuma.sh
```

It creates the first local admin user when needed, reconciles Git-managed project monitors, and creates or updates the core `ops-board` status page.

## Core Status Page

`monitors` contains the Ops Board baseline: Homepage, Uptime Kuma, SigNoz, Plane, and the optional playground API. Those monitors are the only entries on the `ops-board` status page, which Homepage reads through its widget.

Do not add ordinary project monitors to that page. A project outage must not make the monitoring platform itself appear down.

## Project Monitor Registry

`project_monitors` is the source of truth for real project health checks. Add one entry per anonymous HTTP health endpoint:

```yaml
project_monitors:
  - id: spark-h3-gateway
    name: Spark H3 Gateway
    url: http://100.64.35.71:8090/health
    accepted_statuscodes: ["200-299"]
```

`id` is a unique, stable lowercase kebab-case key. It is not a display label; do not change it just because the service name changes. `name` is the label shown in Uptime Kuma and may be renamed safely. `url` must begin with `http://` or `https://` and must be reachable from the Uptime Kuma container on the Ops Board host.

Optional settings are all Git-managed:

| Field | Default | Use |
|-------|---------|-----|
| `accepted_statuscodes` | `["200-299"]` | Successful response ranges. |
| `enabled` | `true` | Set `false` to keep the monitor without checking it. |
| `interval_seconds` | `60` | Time between checks. |
| `retry_interval_seconds` | `60` | Delay between retries. |
| `max_retries` | `0` | Retry count before reporting failure. |
| `max_redirects` | `10` | Redirect limit for HTTP checks. |
| `verify_tls` | `true` | Keep TLS certificate verification enabled for HTTPS monitors. |

The current registry supports anonymous `GET` health checks. Do not put credentials, authorization headers, or notification-provider secrets in this file. Add an authenticated check only through a later secrets-backed design.

## Reconciliation Rules

- A new registry entry creates a Uptime Kuma monitor.
- A changed owned entry updates its URL, label, enabled state, and registry-managed HTTP settings.
- A removed entry is not deleted; pause, archive, or delete it deliberately in Uptime Kuma when retiring the service.
- A manual monitor with the same name is never adopted. Bootstrap stops with a clear error so the maintainer can resolve the collision.
- Existing notification bindings and other unmanaged Uptime Kuma fields are preserved during an owned-monitor update.

Manual monitor creation remains a fallback only when bootstrap cannot run. Do not manually recreate a registry-owned monitor: fix the registry or the bootstrap error instead.

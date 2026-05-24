# Uptime Kuma Monitors

Create these monitors manually in Uptime Kuma after first-account setup.

Use `host.docker.internal` for same-host checks from the Uptime Kuma container. The compose file maps `host.docker.internal` through Docker's host gateway.

## Initial Monitors

| Name | Type | URL | Expected |
|------|------|-----|----------|
| SigNoz UI | HTTP(s) | `http://host.docker.internal:8080/api/v1/health` | `200` |
| SigNoz Collector | HTTP(s) | `http://host.docker.internal:13133/` | `200` |

## Add After Homepage

| Name | Type | URL | Expected |
|------|------|-----|----------|
| Homepage | HTTP(s) | `http://host.docker.internal:3000` | `200` |

## Add After Plane

| Name | Type | URL | Expected |
|------|------|-----|----------|
| Plane | HTTP(s) | `http://host.docker.internal:8082` | `200`, `302`, or app-specific healthy response |

## Status Page

Create one status page:

```text
Slug: ops-board
Title: Ops Board
```

Add the monitors above to the status page as each stack becomes available.

# Uptime Kuma Monitors

Uptime Kuma is the v1 status source for Ops Board endpoint health.

The code-backed source of truth is `stacks/uptime-kuma/bootstrap/monitors.yaml`.

Run the bootstrap after Uptime Kuma is running:

```powershell
.\scripts\bootstrap-uptime-kuma.ps1
```

The script creates the first local admin user when setup is needed, creates any missing baseline monitors, and creates or updates the `ops-board` status page. It is safe to re-run.

Manual monitor creation is a fallback when the bootstrap script cannot run. Use `host.docker.internal` for same-host checks from the Uptime Kuma container. The compose file maps `host.docker.internal` through Docker's host gateway.

## Status Page

Create one public status page inside Uptime Kuma:

```text
Slug: ops-board
Title: Ops Board
```

Add the core monitors to this status page after each monitor is created.

## Core Ops Board Monitors

| Name | Type | URL | Expected |
|------|------|-----|----------|
| Homepage | HTTP(s) | `http://host.docker.internal:3000` | `200` |
| Uptime Kuma | HTTP(s) | `http://host.docker.internal:3001` | `200` or first-run redirect |
| SigNoz UI | HTTP(s) | `http://host.docker.internal:8080/api/v1/health` | `200` |
| SigNoz Collector | HTTP(s) | `http://host.docker.internal:13133/` | `200` |
| Plane | HTTP(s) | `http://host.docker.internal:8082` | `200`, `302`, `307`, or `308` |

## Onboarding Playground Monitor

Create this monitor when the dummy API is running:

| Name | Type | URL | Expected |
|------|------|-----|----------|
| Dummy API Health | HTTP(s) | `http://host.docker.internal:18080/health` | `200` |

If the dummy API is stopped, pause the monitor instead of treating the red status as an Ops Board failure.

## Setup Notes

- Use monitor names exactly as listed so screenshots, docs, and future automation refer to the same labels.
- Keep the `ops-board` status page slug; Homepage's Uptime Kuma widget reads this slug.
- Add or change baseline monitors in `stacks/uptime-kuma/bootstrap/monitors.yaml`, then re-run `.\scripts\bootstrap-uptime-kuma.ps1`.
- Do not add Healthchecks for v1. Revisit that only after a real scheduled-job pilot shows Uptime Kuma is not enough.

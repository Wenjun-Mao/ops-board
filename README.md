# Ops Board

Self-hosted operations board for monitoring and managing projects across local machines, VPSs, countries, and cloud providers.

The repo is organized as independent Docker Compose stacks. Tailscale is the first access layer; public reverse proxy services are intentionally deferred.

## Stacks

| Stack | Purpose | Status |
|-------|---------|--------|
| SigNoz | Central observability for logs, traces, metrics, and telemetry ingestion | Active |
| Uptime Kuma | Uptime and endpoint monitoring | Planned |
| Homepage | Private dashboard and service directory | Planned |
| Plane | Project and kanban management | Planned |
| Healthchecks | Scheduled job monitoring | Optional |

## Layout

```text
ops-board/
  README.md
  .env.example
  .gitignore

  access/
    tailscale.md

  scripts/
    backup.ps1
    restore.ps1
    status.ps1
    update-stack.ps1

  stacks/
    signoz/
      compose.yaml
      otel-collector-config.yaml
      common/
      docs/
      README.md
```

## Quick Start

Use `.env.example` as a reference for local settings. For stack-specific Compose variables, export them in your shell or copy the relevant values into that stack's `.env` file.

Start SigNoz:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml up -d --remove-orphans
```

Open the SigNoz UI:

```text
http://localhost:8080
```

If this host is joined to Tailscale, use the host's MagicDNS name from other tailnet devices:

```text
http://<tailscale-hostname>:8080
```

## Access Model

Tailscale is the private network boundary for now.

- Do not add Caddy, Traefik, or nginx yet.
- Keep stack ports bound explicitly for local and tailnet access.
- Use Tailscale MagicDNS names in docs and future dashboards.

See `access/tailscale.md` for endpoint conventions.

## Stack Commands

Show SigNoz status:

```powershell
.\scripts\status.ps1 -Stack signoz
```

Update SigNoz:

```powershell
.\scripts\update-stack.ps1 -Stack signoz
```

Remove orphaned containers during an update only when you intentionally want cleanup:

```powershell
.\scripts\update-stack.ps1 -Stack signoz -RemoveOrphans
```

Stop SigNoz while preserving volumes:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml down
```

Reset SigNoz and wipe its named volumes:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml down -v
```

Backup and restore scripts are placeholders until stack-specific backup jobs are defined:

```powershell
.\scripts\backup.ps1
.\scripts\restore.ps1 -BackupPath <path>
```

## Current Priorities

1. Add Uptime Kuma.
2. Add Homepage after monitored services have stable URLs.
3. Define real backup/restore jobs before adding heavier stateful services.
4. Add Plane after backup habits are in place.

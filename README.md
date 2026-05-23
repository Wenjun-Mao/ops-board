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
  HANDOFF.md
  .env.example                  (planned)
  .gitignore                    (planned)

  access/                       (planned)
    tailscale.md

  scripts/                      (planned)
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

The `access/tailscale.md` guide is planned for the next documentation pass.

## Stack Commands

Stop SigNoz while preserving volumes:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml down
```

Reset SigNoz and wipe its named volumes:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml down -v
```

Planned helper scripts will later wrap common status, backup, restore, and update workflows under `scripts/`.

## Current Priorities

1. Keep SigNoz running from `stacks/signoz/`.
2. Document Tailscale access.
3. Add Uptime Kuma.
4. Add Homepage after monitored services have stable URLs.
5. Add backup/update automation before adding Plane.

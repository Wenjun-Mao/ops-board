# Ops Board

Self-hosted operations board for monitoring and managing projects across local machines, VPSs, countries, and cloud providers.

The repo is organized as independent Docker Compose stacks. Tailscale is the first access layer; public reverse proxy services are intentionally deferred.

## Stacks

| Stack | Purpose | Status |
|-------|---------|--------|
| SigNoz | Central observability for logs, traces, metrics, and telemetry ingestion | Active |
| Uptime Kuma | Uptime and endpoint monitoring | Active |
| Homepage | Private dashboard and service directory | Active |
| Plane | Project and kanban management | Active |
| Healthchecks | Scheduled job monitoring | Optional later |

The root `compose.yaml` is the normal full-board entrypoint. It uses Docker Compose `include` to pull in the per-stack Compose files, so `stacks/signoz/compose.yaml`, `stacks/uptime-kuma/compose.yaml`, `stacks/homepage/compose.yaml`, and `stacks/plane/compose.yaml` remain the source of truth for their services.

The core rollout is active: start SigNoz first, Uptime Kuma second, Homepage third, and Plane last.

## Layout

```text
ops-board/
  README.md
  compose.yaml
  .env.example
  .gitignore

  access/
    tailscale.md

  scripts/
    README.md
    backup.ps1
    init-local-config.ps1
    restore.ps1
    status.ps1
    update-stack.ps1

  secrets/
    .gitignore

  stacks/
    signoz/
      compose.yaml
      otel-collector-config.yaml
      common/
      docs/
      README.md

    uptime-kuma/
      compose.yaml
      docs/
      README.md

    homepage/
      compose.yaml
      config/
        bookmarks.yaml
        services.yaml
        settings.yaml
        widgets.yaml
      README.md

    plane/
      compose.yaml
      plane.env.example
      README.md
```

## Quick Start

Create local config and Docker secret files:

```powershell
.\scripts\init-local-config.ps1
```

This creates ignored local files:

- `.env`
- `secrets/signoz_jwt_secret`
- `secrets/plane_secret_key`
- `secrets/plane_postgres_password`
- `secrets/plane_rabbitmq_password`
- `secrets/plane_minio_password`

This also creates the ignored `stacks/plane/plane.env` file when it is missing.

Start Ops Board:

```powershell
docker compose --env-file .env -f compose.yaml up -d
```

Open the SigNoz UI:

```text
http://localhost:8080
```

If this host is joined to Tailscale, use the host's MagicDNS name from other tailnet devices:

```text
http://<tailscale-hostname>:8080
```

## Clean Rebuild From Separate Projects

During this development phase, it is safe to wipe local stack data and rebuild under the root `ops-board` project:

```powershell
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml down -v
docker compose --env-file .env -f stacks/homepage/compose.yaml down -v
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml down -v
docker compose --env-file .env -f stacks/signoz/compose.yaml down -v
docker compose --env-file .env -f compose.yaml up -d
```

This deletes local Docker volumes for these stacks. Remove `-v` from each `down` command when preserving data becomes important.

## Access Model

Tailscale is the private network boundary for now.

- Do not add Caddy, Traefik, or nginx yet.
- Keep stack ports bound explicitly for local and tailnet access.
- Use Tailscale MagicDNS names in docs and future dashboards.

See `access/tailscale.md` for endpoint conventions.

## Config And Secrets

Use `.env` for non-secret runtime knobs such as image tags, ports, hostnames, and backup paths. Use Docker secret files under `secrets/` for credentials and token material.

The SigNoz stack currently uses one Docker secret:

```text
secrets/signoz_jwt_secret
```

Plane uses ignored secret material to populate its stack-local `stacks/plane/plane.env` file:

```text
secrets/plane_secret_key
secrets/plane_postgres_password
secrets/plane_rabbitmq_password
secrets/plane_minio_password
```

Both `.env` and secret files are ignored by Git. Regenerate them with `.\scripts\init-local-config.ps1 -Force` only when you intentionally want to overwrite local settings and rotate local stack secrets.

## Stack Commands

See `scripts/README.md` for the full script reference.

Show Ops Board status:

```powershell
.\scripts\status.ps1
```

Use individual stack names only when intentionally operating a stack outside the root aggregator:

```powershell
.\scripts\status.ps1 -Stack signoz
.\scripts\status.ps1 -Stack uptime-kuma
.\scripts\status.ps1 -Stack homepage
.\scripts\status.ps1 -Stack plane
```

Update Ops Board:

```powershell
.\scripts\update-stack.ps1
```

Remove orphaned containers during an update only when you intentionally want cleanup:

```powershell
.\scripts\update-stack.ps1 -RemoveOrphans
```

Stop Ops Board while preserving volumes:

```powershell
docker compose --env-file .env -f compose.yaml down
```

Reset Ops Board and wipe its named volumes:

```powershell
docker compose --env-file .env -f compose.yaml down -v
```

Backup and restore scripts are placeholders until stack-specific backup jobs are defined:

```powershell
.\scripts\backup.ps1
.\scripts\restore.ps1 -BackupPath <path>
```

## Current Priorities

1. Create the Uptime Kuma first admin account, status page, and monitors.
2. Finish stack-specific backup and restore jobs.
3. Decide whether Healthchecks adds value beyond Uptime Kuma.
4. Revisit a reverse proxy only after Tailscale-first access feels limiting.

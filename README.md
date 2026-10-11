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
    bootstrap-uptime-kuma.sh
    init-local-config.sh
    smoke-day1.sh
    status.sh
    update-stack.sh
    lib/
      ops-board.sh
    tests/
      test-linux-operator-scripts.sh
    backup.ps1
    bootstrap-uptime-kuma.ps1
    init-local-config.ps1
    restore.ps1
    smoke-day1.ps1
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

Linux is the default operator environment. On `HP-15`, use the Tailscale/MagicDNS hostname in generated browser-facing URLs:

```bash
./scripts/init-local-config.sh --host hp-15
```

This creates ignored local files:

- `.env`
- `secrets/signoz_jwt_secret`
- `secrets/plane_secret_key`
- `secrets/plane_postgres_password`
- `secrets/plane_rabbitmq_password`
- `secrets/plane_minio_password`
- `secrets/uptime_kuma_admin_password`

This also creates the ignored `stacks/plane/plane.env` file when it is missing.

Start Ops Board:

```bash
docker compose --env-file .env -f compose.yaml up -d
```

Bootstrap Uptime Kuma, then run the board smoke:

```bash
./scripts/bootstrap-uptime-kuma.sh
./scripts/smoke-day1.sh --skip-onboarding
```

Open Homepage:

```text
http://hp-15:3000
```

Use `localhost` only from a shell or browser running directly on the deployment host. From other tailnet devices, use the host's MagicDNS name:

```text
http://<tailscale-hostname>:3000
```

## Clean Rebuild From Separate Projects

During this development phase, it is safe to wipe local stack data and rebuild under the root `ops-board` project:

```bash
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
- Use Tailscale MagicDNS names in docs, `.env`, Plane URLs, Homepage links, and future dashboards.

See `access/tailscale.md` for endpoint conventions.

## Config And Secrets

Use `.env` for non-secret runtime knobs such as image tags, ports, hostnames, and backup paths. Use Docker secret files under `secrets/` for credentials and token material.

The SigNoz stack currently uses one Docker secret:

```text
secrets/signoz_jwt_secret
```

Uptime Kuma uses one local admin secret for its code-backed first-run bootstrap:

```text
secrets/uptime_kuma_admin_password
```

Plane uses ignored secret material to populate its stack-local `stacks/plane/plane.env` file:

```text
secrets/plane_secret_key
secrets/plane_postgres_password
secrets/plane_rabbitmq_password
secrets/plane_minio_password
```

Both `.env` and secret files are ignored by Git. Regenerate them with `./scripts/init-local-config.sh --host hp-15 --force` only when you intentionally want to overwrite local settings and rotate local stack secrets.

## Stack Commands

See `scripts/README.md` for the full script reference.

Show Ops Board status:

```bash
./scripts/status.sh
```

Select a service group within the root `ops-board` project (the default context):

```bash
./scripts/status.sh --stack signoz
./scripts/status.sh --stack uptime-kuma
./scripts/status.sh --stack homepage
./scripts/status.sh --stack plane
```

For intentionally standalone installations, add `--context standalone` and a named
stack. Never use that context to maintain HP-15's aggregated deployment.

Generic pull/check (retains existing containers; not a release migration):

```bash
./scripts/update-stack.sh
```

Changed images or stopped writers are refused; `--remove-orphans` is unsupported.
For scoped cold backups, fresh isolated restores, passive readiness and reviewed
release stages, see [maintenance and recovery](scripts/maintenance/README.md).

Stop Ops Board while preserving volumes:

```bash
docker compose --env-file .env -f compose.yaml down
```

Reset Ops Board and wipe its named volumes:

```bash
docker compose --env-file .env -f compose.yaml down -v
```

Config backup and restore scripts protect allowlisted non-secret repo config and docs. Stack data backup jobs are still future work:

```powershell
.\scripts\backup.ps1
.\scripts\restore.ps1 -BackupPath <path>
```

The old `*.ps1` operator scripts remain for compatibility during the transition, but Linux `*.sh` scripts are the default operator path.

## Monitoring And Onboarding Docs

Use these docs when operating the board or connecting projects to it:

- `docs/monitoring/ops-board-user-manual.md` - how to use Ops Board day to day.
- `docs/monitoring/first-run-accounts.md` - SigNoz and Plane first admin/workspace setup checklist.
- `docs/onboarding/human-guide.md` - agentless health monitoring first, then optional telemetry.
- `docs/onboarding/onboarding-contract.md` - health-monitor registry and optional telemetry contract.
- `docs/onboarding/onboarding-design-playbook.md` - reusable lessons for designing future onboarding flows.
- `docs/onboarding/codex-guide.md` - machine-friendly onboarding instructions for Codex sessions.
- `examples/onboarding/README.md` - dummy API/job playground for testing the experience.

## Current Priorities

1. Operate the first Git-managed project health monitor, then add telemetry only where deeper evidence is useful.
2. Finish stack-specific backup and restore jobs.
3. Decide whether Healthchecks adds value beyond Uptime Kuma after a real scheduled-job pilot.
4. Revisit a reverse proxy only after Tailscale-first access feels limiting.

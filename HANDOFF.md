# Ops Board Handoff

Date: 2026-05-23

This repo is being renamed from `signoz-stack` to `ops-board`.

The goal is to evolve it from a single SigNoz stack into a self-hosted operations board for monitoring and managing projects across local machines, VPSs, countries, and cloud providers.

## Current Decision

- New repo name: `ops-board`
- Primary access layer for now: Tailscale
- Reverse proxy: deferred
- Initial working stack: SigNoz
- Planned later stacks: Uptime Kuma, Homepage, Plane, optional Healthchecks

## Important Before Recloning

The current local working tree has uncommitted changes. Commit and push them before renaming/recloning, or the fresh clone will not include the upgraded SigNoz work or this handoff.

Current remote:

```powershell
origin https://github.com/Wenjun-Mao/signoz-stack.git
```

Recommended sequence:

```powershell
git status
git add README.md stacks/signoz/compose.yaml stacks/signoz/otel-collector-config.yaml stacks/signoz/common/signoz/otel-collector-opamp-config.yaml HANDOFF.md
git commit -m "Update SigNoz stack and add ops-board handoff"
git push
```

Then rename the GitHub repo from `signoz-stack` to `ops-board`, reclone it, and restart from this document.

## Current Local Runtime State

The SigNoz stack was clean rebuilt from scratch on 2026-05-23.

Old Docker volumes were wiped:

- `signoz-clickhouse`
- `signoz-sqlite`
- `signoz-zookeeper-1`
- `signoz-vector-data`

Current running services were verified after rebuild:

- `signoz` is healthy on `0.0.0.0:8080`
- `signoz-clickhouse` is healthy
- `signoz-zookeeper-1` is healthy
- `signoz-otel-collector` is running on `0.0.0.0:4317`, `0.0.0.0:4318`, and `0.0.0.0:13133`
- `signoz-telemetrystore-migrator` exited `0`
- `signoz-init-clickhouse` exited `0`

Health checks passed:

```powershell
Invoke-WebRequest http://localhost:8080/api/v1/health
Invoke-WebRequest http://localhost:13133/
docker exec signoz-clickhouse clickhouse-client -q "SHOW DATABASES"
```

Expected ClickHouse databases:

- `signoz_analytics`
- `signoz_logs`
- `signoz_metadata`
- `signoz_meter`
- `signoz_metrics`
- `signoz_traces`

Because `signoz-sqlite` was wiped, the SigNoz UI should ask for first-account setup again.

## Current SigNoz Pins

Rendered images:

```text
signoz/signoz:v0.125.1
signoz/signoz-otel-collector:v0.144.4
clickhouse/clickhouse-server:25.5.6
signoz/zookeeper:3.7.1
```

Do not bump ClickHouse independently just because newer ClickHouse tags exist. The current upstream SigNoz Docker compose still pins ClickHouse `25.5.6`.

## Current Uncommitted File Changes

Files changed:

- `README.md`
- `stacks/signoz/compose.yaml`
- `stacks/signoz/otel-collector-config.yaml`
- `stacks/signoz/common/signoz/otel-collector-opamp-config.yaml`
- `HANDOFF.md`

Meaning of the changes:

- Upgraded SigNoz from `v0.111.0` to `v0.125.1`
- Upgraded SigNoz OTel collector from `v0.142.0` to `v0.144.4`
- Replaced old separate schema migrator services with `signoz-telemetrystore-migrator`
- Added OpAMP manager config at `stacks/signoz/common/signoz/otel-collector-opamp-config.yaml`
- Added `metadataexporter` to the collector config
- Documented current stack pins in `README.md`

## Target Repo Shape

Recommended target structure after the repo is renamed:

```text
ops-board/
  README.md
  HANDOFF.md
  .env.example
  .gitignore

  stacks/
    signoz/
      compose.yaml
      common/
      docs/
      README.md

    uptime-kuma/
      compose.yaml
      README.md

    homepage/
      compose.yaml
      config/
        services.yaml
        widgets.yaml
        settings.yaml
      README.md

    plane/
      compose.yaml
      plane.env.example
      README.md

    healthchecks/
      compose.yaml
      .env.example
      README.md

  access/
    tailscale.md

  scripts/
    backup.ps1
    restore.ps1
    update-stack.ps1
    status.ps1
```

Prefer `stacks/<service>/` over root-level service folders so the root remains a control surface instead of a drawer.

## Tailscale-First Access Model

For now, do not add Caddy, Traefik, or nginx.

Use Tailscale/MagicDNS as the private access layer:

- SigNoz UI: `http://<tailscale-hostname>:8080`
- OTLP HTTP: `http://<tailscale-hostname>:4318/v1/logs`
- OTLP gRPC: `<tailscale-hostname>:4317`
- Collector health: `http://<tailscale-hostname>:13133/`

Later, a reverse proxy can be added under `access/` or `reverse-proxy/` if public TLS endpoints are needed.

## Recommended Next Session Plan

After recloning the renamed `ops-board` repo:

1. Confirm the repo is clean and the remote points to `ops-board`.
2. Move the current SigNoz stack into `stacks/signoz/`.
3. Update paths inside `stacks/signoz/compose.yaml`.
   - Current compose paths should be relative to `stacks/signoz/`.
   - Bind mounts should use paths such as `./common/...`.
4. Update commands in `README.md` and `docs/ONBOARDING.md`.
5. Add root `.env.example`.
6. Add root `.gitignore`.
7. Add `access/tailscale.md`.
8. Add script placeholders for `backup.ps1`, `restore.ps1`, `update-stack.ps1`, and `status.ps1`.
9. Verify SigNoz still starts from the new path.

Suggested verification after the move:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml config --quiet
docker compose -p signoz -f stacks/signoz/compose.yaml up -d --remove-orphans
Invoke-WebRequest http://localhost:8080/api/v1/health
Invoke-WebRequest http://localhost:13133/
docker compose -p signoz -f stacks/signoz/compose.yaml ps
```

## Naming Rationale

`ops-board` was chosen because it is short, non-personal, and broad enough for:

- monitoring dashboards
- uptime checks
- project boards
- multi-host operations
- local and VPS infrastructure

It also keeps a natural relationship with both monitoring boards and kanban boards.

## Notes For The Next Codex Session

Start with this prompt:

```text
We renamed signoz-stack to ops-board and recloned it. Read HANDOFF.md first. Continue by restructuring the repo into the target ops-board layout, preserving the verified SigNoz stack behavior and using Tailscale as the first access layer. Do not add reverse proxy services yet.
```

Keep changes incremental. The first milestone is only to move SigNoz under `stacks/signoz/` and prove it still runs.

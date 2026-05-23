# Ops Board Handoff

Date: 2026-05-23

This repo was renamed from `signoz-stack` to `ops-board`.

The goal is to evolve it from a single SigNoz stack into a self-hosted operations board for monitoring and managing projects across local machines, VPSs, countries, and cloud providers.

## Current Decision

- New repo name: `ops-board`
- Primary access layer for now: Tailscale
- Reverse proxy: deferred
- Initial working stack: SigNoz
- Planned later stacks: Uptime Kuma, Homepage, Plane, optional Healthchecks

## Current Remote

```powershell
origin https://github.com/Wenjun-Mao/ops-board.git
```

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

## Completed Restructure

The first ops-board restructure moved SigNoz under `stacks/signoz/` and added root conventions for Tailscale-first operation.

Meaningful changes:

- Upgraded SigNoz from `v0.111.0` to `v0.125.1`
- Upgraded SigNoz OTel collector from `v0.142.0` to `v0.144.4`
- Replaced old separate schema migrator services with `signoz-telemetrystore-migrator`
- Added OpAMP manager config at `stacks/signoz/common/signoz/otel-collector-opamp-config.yaml`
- Added `metadataexporter` to the collector config
- Documented current stack pins in `stacks/signoz/README.md`
- Added root `.env.example`, `.gitignore`, `access/tailscale.md`, and helper scripts under `scripts/`

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

## Verification Commands

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

Suggested prompt:

```text
Read HANDOFF.md first. Continue evolving ops-board from the completed SigNoz/Tailscale baseline. The next likely stack is Uptime Kuma. Do not add reverse proxy services yet.
```

Keep changes incremental. Add one stack at a time and verify it before expanding the board.

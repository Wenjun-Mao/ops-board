# SigNoz Stack

Shared SigNoz observability stack for centralized logs, traces, metrics, and OTLP ingestion across multiple projects.

## Quick Start

From the repo root:

```powershell
.\scripts\init-local-config.ps1
docker compose --env-file .env -f stacks/signoz/compose.yaml up -d
```

Compose variables live in the repo root `.env`. Secret values live in ignored files under `secrets/` and are mounted with Docker secrets. This stack declares `name: signoz`, so direct Compose commands do not need `-p signoz`.

Open UI:

```text
http://localhost:8080
```

From another device on the same Tailscale tailnet:

```text
http://<tailscale-hostname>:8080
```

## Services

Starting this compose file starts the full SigNoz stack:

| Service | Role |
|---------|------|
| `signoz` | Web UI and application server |
| `otel-collector` | OTLP logs, traces, and metrics ingestion |
| `clickhouse` | Telemetry storage |
| `zookeeper-1` | ClickHouse coordination |
| `init-clickhouse` | One-shot ClickHouse user script setup |
| `signoz-telemetrystore-migrator` | One-shot telemetry schema migrations |

The one-shot services exit with code `0` after setup. Use `.\scripts\status.ps1 -Stack signoz` to see both running and completed services.

## Current Stack Pins

| Component | Image |
|-----------|-------|
| SigNoz | `signoz/signoz:v0.125.1` |
| SigNoz OTel Collector | `signoz/signoz-otel-collector:v0.144.4` |
| ClickHouse | `clickhouse/clickhouse-server:25.5.6` |
| ZooKeeper | `signoz/zookeeper:3.7.1` |

ClickHouse stays at `25.5.6` because that is the version currently pinned by the upstream SigNoz Docker Compose layout.

## Published Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 8080 | HTTP | SigNoz web dashboard |
| 4317 | gRPC | OTLP receiver |
| 4318 | HTTP | OTLP receiver |
| 13133 | HTTP | Collector health check |

## Tailscale Endpoints

Use the host's Tailscale MagicDNS name from other tailnet devices:

```text
http://<tailscale-hostname>:8080
http://<tailscale-hostname>:4318/v1/logs
http://<tailscale-hostname>:4318/v1/traces
http://<tailscale-hostname>:4318/v1/metrics
<tailscale-hostname>:4317
http://<tailscale-hostname>:13133/
```

## Restricted Network Setup

If the host cannot reach GitHub, pre-seed the ClickHouse init binary tarball locally.

1. Download the correct archive on a machine with internet:
   - `histogram-quantile_linux_amd64.tar.gz` for `x86_64/amd64`
   - `histogram-quantile_linux_arm64.tar.gz` for `aarch64/arm64`
2. Copy and rename it to:
   - `stacks/signoz/common/clickhouse/user_scripts/histogram-quantile.tar.gz`
3. Start stack:
   - `docker compose --env-file .env -f stacks/signoz/compose.yaml up -d`
4. Verify init succeeded:
   - `docker logs signoz-init-clickhouse --tail 100`
   - `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"`

Optional: if you have an accessible mirror URL, set `HISTOGRAM_QUANTILE_URL` in the repo root `.env`. The compose file passes that value into `signoz-init-clickhouse`.

## Onboarding Projects

See `docs/ONBOARDING.md`.

## Stop And Reset

Stop while keeping data:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml down
```

Full reset:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml down -v
```

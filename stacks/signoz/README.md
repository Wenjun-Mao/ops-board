# SigNoz Stack

Shared SigNoz observability stack for centralized logs, traces, metrics, and OTLP ingestion across multiple projects.

## Quick Start

These standalone commands are for a fresh `signoz` project. HP-15 already uses
root project `ops-board`: do not apply standalone commands to that deployment.
Use the gated [maintenance workflow](maintenance/README.md) for existing state.

From the repo root:

```bash
./scripts/init-local-config.sh --host hp-15
docker compose --env-file .env -f stacks/signoz/compose.yaml up -d
```

Compose variables live in the repo root `.env`. Secret values live in ignored files under `secrets/` and are mounted with Docker secrets. This stack declares `name: signoz`, so direct Compose commands do not need `-p signoz`.

Open the UI from the deployment host:

```text
http://localhost:8080
```

From another device on the same Tailscale tailnet, use the host's Tailscale/MagicDNS name:

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

The one-shot services exit with code `0` after setup. Use `./scripts/status.sh --stack signoz` to see both running and completed services.

## Current Stack Pins

| Component | Image |
|-----------|-------|
| SigNoz | `signoz/signoz:v0.145.0` |
| SigNoz OTel Collector / Migrator | `signoz/signoz-otel-collector:v0.144.12` |
| ClickHouse / Init | `clickhouse/clickhouse-server:25.12.5` (observed 25.12.5.44) |
| ZooKeeper | `signoz/zookeeper:3.7.1` |

These are the accepted HP-15 deployment and repository defaults, not floating
upstream versions. The ordered four-stop rollout preserved the existing stores
and credentials; see the [live receipt](../../docs/monitoring/maintenance-receipts/2026-10-10-signoz-live.md).
Official bundled Compose was deprecated in v0.130. Paired collector/OpAMP
configuration and gated existing-state upgrades are documented in
[maintenance/README.md](maintenance/README.md). Rendering alone proves no upgrade.

## Lifecycle Contract

The owned read-only collector launcher preserves `migrate sync check`, then
execs the actual collector as PID 1. It forwards TERM/INT only to its initializer
child during that check, reaps it and bounds cancellation; forced KILL is still
exit 137 and an unclean refusal. The server launcher requires a readable,
nonempty existing JWT Docker secret before exec; it never prints the value or
rotates credentials. The active collector uses the paired maintenance YAML and
OpAMP manager configuration. The original `otel-collector-config.yaml` is retained
byte-for-byte as historical baseline evidence; it is no longer the active bind.

The HP-15 launcher installation and readiness-qualified ordinary stop, restart
and cold-restore gates have passed. Its temporary old-child signaling mitigation
is retired; the [installation record](maintenance/README.md#baseline-launcher-installation-gate)
must not become the backup path. Long-running services use `unless-stopped`;
one-shot jobs never retry automatically. Fresh startup retains the normal
dependency graph; existing-state maintenance uses explicit gated manual phases.

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

Use the canonical onboarding docs:

- [Human guide](../../docs/onboarding/human-guide.md)
- [Onboarding contract](../../docs/onboarding/onboarding-contract.md)
- [Codex guide](../../docs/onboarding/codex-guide.md)

## Stop And Reset

Standalone project only; not the root-project maintenance or backup workflow.

Stop while keeping data:

```bash
docker compose --env-file .env -f stacks/signoz/compose.yaml down
```

Full reset:

```bash
docker compose --env-file .env -f stacks/signoz/compose.yaml down -v
```

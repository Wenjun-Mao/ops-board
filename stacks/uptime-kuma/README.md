# Uptime Kuma Stack

Private uptime and endpoint monitoring for Ops Board.

## Quick Start

From the repo root:

```bash
./scripts/init-local-config.sh --host hp-15
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml up -d
./scripts/bootstrap-uptime-kuma.sh
```

Open from the deployment host:

```text
http://localhost:3001
```

From another tailnet device, use the host's Tailscale/MagicDNS name:

```text
http://<tailscale-hostname>:3001
```

## First Run

Uptime Kuma first-run setup is code-backed for normal Ops Board development.

The Compose file selects embedded MariaDB, and `./scripts/bootstrap-uptime-kuma.sh` creates the first local admin user from `secrets/uptime_kuma_admin_password`, applies baseline monitors from `bootstrap/monitors.yaml`, and creates or updates the status page with this slug:

```text
ops-board
```

Homepage uses that status page slug for its Uptime Kuma widget.

## Storage

Uptime Kuma stores embedded MariaDB data under `/app/data` in the Docker volume `uptime-kuma-data`.

Keep this data on local Docker-managed storage. Do not move it to NFS, cloud sync folders, or remote filesystems unless that storage model has been deliberately tested for this workload.

## Monitor Targets

See `docs/monitors.md`.

## Commands

Show status:

```bash
./scripts/status.sh --stack uptime-kuma
```

Stop while preserving data:

```bash
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml down
```

Reset and delete the Uptime Kuma volume:

```bash
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml down -v
```

# Uptime Kuma Stack

Private uptime and endpoint monitoring for Ops Board.

## Quick Start

From the repo root:

```powershell
.\scripts\init-local-config.ps1
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml up -d
```

Open:

```text
http://localhost:3001
```

From another tailnet device, use:

```text
http://<tailscale-hostname>:3001
```

## First Run

Create the first Uptime Kuma admin account in the web UI.

Create a status page with this slug:

```text
ops-board
```

Homepage uses that status page slug for its Uptime Kuma widget.

## Storage

Uptime Kuma stores SQLite data under `/app/data` in the Docker volume `uptime-kuma-data`.

Keep this data on local Docker-managed storage. Do not move it to NFS, cloud sync folders, or remote filesystems because SQLite needs reliable file locking.

## Monitor Targets

See `docs/monitors.md`.

## Commands

Show status:

```powershell
.\scripts\status.ps1 -Stack uptime-kuma
```

Stop while preserving data:

```powershell
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml down
```

Reset and delete the Uptime Kuma volume:

```powershell
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml down -v
```

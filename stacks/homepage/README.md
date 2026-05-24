# Homepage Stack

Private service directory for Ops Board.

## Quick Start

From the repo root:

```powershell
.\scripts\init-local-config.ps1
docker compose --env-file .env -f stacks/homepage/compose.yaml up -d
```

Open:

```text
http://localhost:3000
```

From another tailnet device:

```text
http://<tailscale-hostname>:3000
```

## Configuration

Homepage config lives in `config/`.

The compose file does not mount the Docker socket. Service links and widgets are explicit so the dashboard works the same way across local machines and VPS hosts.

## Uptime Kuma Widget

The Uptime Kuma widget reads from the status page slug in `.env`:

```dotenv
UPTIME_KUMA_STATUS_SLUG=ops-board
```

Create that status page in Uptime Kuma before expecting the widget to show useful data.

## Commands

Show status:

```powershell
.\scripts\status.ps1 -Stack homepage
```

Stop:

```powershell
docker compose --env-file .env -f stacks/homepage/compose.yaml down
```

# Homepage Stack

Private service directory for Ops Board.

## Quick Start

From the repo root:

```bash
./scripts/init-local-config.sh --host hp-15
docker compose --env-file .env -f stacks/homepage/compose.yaml up -d
```

Open from the deployment host:

```text
http://localhost:3000
```

From another tailnet device, use the host's Tailscale/MagicDNS name:

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

Run `./scripts/bootstrap-uptime-kuma.sh` before expecting the widget to show useful data. The bootstrap creates or updates the `ops-board` status page.

## Commands

Show status:

```bash
./scripts/status.sh --stack homepage
```

Stop:

```bash
docker compose --env-file .env -f stacks/homepage/compose.yaml down
```

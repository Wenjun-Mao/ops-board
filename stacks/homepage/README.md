# Homepage Stack

Private service directory for Ops Board.

## Quick Start

From the repo root:

```bash
./scripts/init-local-config.sh --host hp-15
docker compose --env-file .env -f compose.yaml up -d --no-deps homepage
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

The reviewed release is v2.4.0. `HOMEPAGE_AUTH_ENABLED=false` deliberately keeps
the existing private tailnet dashboard without another login. Keep
`HOMEPAGE_ALLOWED_HOSTS` restricted to the deployment's actual names. This is not
a public unauthenticated deployment recommendation.

Homepage v2 enforces the request-address allowlist. The existing Kuma monitor
uses `http://host.docker.internal:3000`; retain that exact address in
`HOMEPAGE_ALLOWED_HOSTS` alongside localhost, loopback and the actual public host
entries. Browser access through the tailnet name alone does not prove this monitor
path works. Do not change the monitor URL, use `*`, or disable hostname validation
to hide a rejected address. Existing `.env` files are not rewritten by the example;
the operator must explicitly add the alias while preserving current entries.
`init-local-config.sh --host` includes the explicit internal alias alongside
the local/public allowlist; existing manually maintained lists must retain it too.
The example and fallback cover published port 3000 only. With a custom
`HOMEPAGE_PORT`, explicitly set every allowed `host:published-port` entry,
including `host.docker.internal:<published-port>`, to match the actual requests.

### BrowserLinksAndServerProbes

Browser `href` values use public URLs reachable from the user's tailnet device.
Server-side widgets and health pings use separate internal URLs reachable from
the Homepage container, following the existing Kuma public/internal split.
SigNoz keeps `SIGNOZ_PUBLIC_URL` for its browser link and uses
`SIGNOZ_INTERNAL_URL` (default `http://host.docker.internal:8080`) for
`/api/v1/health`. A healthy public endpoint does not prove container-side reachability.
With a custom SigNoz published port, explicitly update `SIGNOZ_INTERNAL_URL` to
that port. Existing `.env` files can omit this key to use the default; no monitor,
DNS, network membership, endpoint or authentication policy changes are required.

HP-15 uses the root `ops-board` project. A stack-local Compose file is only for an
intentionally separate deployment; do not use it to update the existing HP-15
container. See [maintenance and recovery](../../scripts/maintenance/README.md).

## Uptime Kuma Widget

The Uptime Kuma widget reads from the status page slug in `.env`:

```dotenv
UPTIME_KUMA_STATUS_SLUG=ops-board
```

Run `./scripts/bootstrap-uptime-kuma.sh` before expecting the widget to show useful data. The bootstrap creates or updates the `ops-board` status page.

That widget represents Ops Board infrastructure only. Git-managed project monitors remain visible in the private Uptime Kuma dashboard and do not change Homepage's platform-health signal.

## Commands

Show status:

```bash
./scripts/status.sh --stack homepage
```

Stop:

```bash
docker compose --env-file .env -f compose.yaml stop homepage
```

# Plane Stack

Project and kanban management for Ops Board.

## Edition

This repo starts with Plane Community Edition.

Community Edition is AGPL v3 and is the best fit for this repo's first Plane pass because it is auditable and self-contained. Commercial Edition can be evaluated after the Community stack is working.

## Install Model

Do not hand-write Plane's compose file from memory.

Use Plane's official setup flow, or the equivalent official release assets, to acquire the current Community Edition `docker-compose.yaml` and `plane.env`, then adapt the generated files into this folder with the smallest possible changes:

- rename `docker-compose.yaml` to `compose.yaml`
- add top-level `name: plane`
- avoid port `8080` because SigNoz already uses it
- keep `plane.env` ignored
- keep `plane.env.example` sanitized and committed

This compose file was acquired from Plane Community Edition `v1.3.1`.
The local `plane.env` uses ignored secret files created by `scripts/init-local-config.sh` for database, RabbitMQ, MinIO, and app secret values.

Prepared v1.4.2 application and independent dependency release layers are in
[the staged maintenance guide](maintenance/README.md). They are opt-in candidates,
not deployed defaults. Preserve existing credentials and Rabbit node identity;
never run a blanket upgrade or implicit migration against existing state.

Worker/beat use the [read-only exec launcher](lifecycle/README.md) for ordinary
Docker TERM delivery. API/migrator retain official scripts; existing containers
need manager-coordinated scoped recreation before this source fix is active.

## Access

From the deployment host:

```text
http://localhost:8082
```

From another tailnet device, use the host's Tailscale/MagicDNS name:

```text
http://<tailscale-hostname>:8082
```

## Commands

Show status:

```bash
./scripts/status.sh --stack plane
```

HP-15 uses root project `ops-board`. Use the stage guide for startup/maintenance
of that existing deployment. Intentionally standalone fresh deployments only:

```bash
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml up -d
```

Stop that standalone deployment:

```bash
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml down
```

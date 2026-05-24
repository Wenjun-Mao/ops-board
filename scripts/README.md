# Scripts

These scripts are repo-level helpers for local operations. Run them from any working directory; each script resolves the repo root from its own path.

All stack-aware scripts look for `stacks/<stack>/compose.yaml`. Each active stack owns its Docker Compose project name with top-level `name:`, so normal commands do not need `-p`.

## init-local-config.ps1

Creates local runtime config that must not be committed:

- `.env`
- `secrets/signoz_jwt_secret`
- `secrets/plane_secret_key`
- `secrets/plane_postgres_password`
- `secrets/plane_rabbitmq_password`
- `secrets/plane_minio_password`

Use it after cloning the repo, before starting a stack for the first time:

```powershell
.\scripts\init-local-config.ps1
```

Use `-Force` only when you intentionally want to overwrite `.env` from `.env.example` and rotate local stack secrets:

```powershell
.\scripts\init-local-config.ps1 -Force
```

Rotating `secrets/signoz_jwt_secret` can invalidate existing SigNoz tokens or sessions. Rotating Plane secrets requires updating `stacks/plane/plane.env` and recreating the Plane stack. Restart affected stacks after rotation.

## status.ps1

Shows Docker Compose status for one stack. It includes completed one-shot services such as init and migration jobs, and defaults to SigNoz:

```powershell
.\scripts\status.ps1
```

Use `-Stack` when another stack is added:

```powershell
.\scripts\status.ps1 -Stack uptime-kuma
```

The script includes the root `.env` file automatically when it exists. It also includes stack-local env files when present:

- `stacks/<stack>/.env`
- `stacks/<stack>/<stack>.env`

Common stack names:

```powershell
.\scripts\status.ps1 -Stack signoz
.\scripts\status.ps1 -Stack uptime-kuma
.\scripts\status.ps1 -Stack homepage
.\scripts\status.ps1 -Stack plane
```

## update-stack.ps1

Pulls images for a stack and runs `docker compose up -d`. It defaults to SigNoz:

```powershell
.\scripts\update-stack.ps1
```

Use `-RemoveOrphans` only when you deliberately want Compose to remove containers that are no longer present in the compose file:

```powershell
.\scripts\update-stack.ps1 -Stack signoz -RemoveOrphans
```

For stateful stacks, check the stack README before using this during a version upgrade.

The script includes the root `.env` file first, then stack-local env files when present. Stack-local values override root defaults.

Update a specific stack:

```powershell
.\scripts\update-stack.ps1 -Stack uptime-kuma
.\scripts\update-stack.ps1 -Stack homepage
.\scripts\update-stack.ps1 -Stack plane
```

## backup.ps1

Creates the backup root directory and prints the current backup status:

```powershell
.\scripts\backup.ps1
```

This is currently a placeholder. It does not yet export SigNoz, ClickHouse, or other stack data.

## restore.ps1

Validates that a restore source path exists and prints the current restore status:

```powershell
.\scripts\restore.ps1 -BackupPath <path>
```

This is currently a placeholder. It does not yet restore SigNoz, ClickHouse, or other stack data.

## Direct Docker Compose Commands

Start SigNoz:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml up -d
```

Start all active stacks in rollout order:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml up -d
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml up -d
docker compose --env-file .env -f stacks/homepage/compose.yaml up -d
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml up -d
```

Stop SigNoz while preserving volumes:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml down
```

Reset SigNoz and wipe named volumes:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml down -v
```

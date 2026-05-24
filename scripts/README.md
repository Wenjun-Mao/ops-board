# Scripts

These scripts are repo-level helpers for local operations. Run them from any working directory; each script resolves the repo root from its own path.

All stack-aware scripts look for `stacks/<stack>/compose.yaml`. The SigNoz compose file owns its Docker Compose project name with `name: signoz`, so normal commands do not need `-p signoz`.

## init-local-config.ps1

Creates local runtime config that must not be committed:

- `.env`
- `secrets/signoz_jwt_secret`

Use it after cloning the repo, before starting a stack for the first time:

```powershell
.\scripts\init-local-config.ps1
```

Use `-Force` only when you intentionally want to overwrite `.env` from `.env.example` and rotate the SigNoz JWT secret:

```powershell
.\scripts\init-local-config.ps1 -Force
```

Rotating `secrets/signoz_jwt_secret` can invalidate existing SigNoz tokens or sessions. Restart SigNoz after rotation.

## status.ps1

Shows Docker Compose status for one stack. It includes completed one-shot services such as init and migration jobs, and defaults to SigNoz:

```powershell
.\scripts\status.ps1
```

Use `-Stack` when another stack is added:

```powershell
.\scripts\status.ps1 -Stack uptime-kuma
```

The script includes the root `.env` file automatically when it exists.

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

Stop SigNoz while preserving volumes:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml down
```

Reset SigNoz and wipe named volumes:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml down -v
```

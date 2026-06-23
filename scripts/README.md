# Scripts

These scripts are repo-level helpers for local operations. Run them from any working directory; each script resolves the repo root from its own path.

Linux is the default operator path. The old `*.ps1` scripts remain for compatibility during the transition, but use the `*.sh` scripts for normal deployment and HP-15 validation.

All stack-aware scripts look for root `compose.yaml` when `--stack ops-board` is used. `ops-board` is the default. Individual stack names still resolve to `stacks/<stack>/compose.yaml` for isolated maintenance.

Use the Tailscale/MagicDNS hostname in `.env` for browser-facing URLs. On `HP-15`, that means URLs such as `http://hp-15:3000` and `http://hp-15:8080`. Use `localhost` only from a shell or browser running directly on the deployment host.

## init-local-config.sh

Creates local runtime config that must not be committed:

- `.env`
- `secrets/signoz_jwt_secret`
- `secrets/plane_secret_key`
- `secrets/plane_postgres_password`
- `secrets/plane_rabbitmq_password`
- `secrets/plane_minio_password`
- `secrets/uptime_kuma_admin_password`
- `stacks/plane/plane.env`

Use it after cloning the repo, before starting a stack for the first time:

```bash
./scripts/init-local-config.sh --host hp-15
```

Use `--force` only when you intentionally want to overwrite `.env` from `.env.example` and rotate local stack secrets:

```bash
./scripts/init-local-config.sh --host hp-15 --force
```

Rotating `secrets/signoz_jwt_secret` can invalidate existing SigNoz tokens or sessions. Rotating Plane secrets with `--force` recreates `stacks/plane/plane.env`; recreate affected containers after rotation.

## bootstrap-uptime-kuma.sh

Bootstraps Uptime Kuma after the container is running:

- creates the first local admin user when setup is needed
- logs in through Uptime Kuma's Socket.IO app contract
- creates missing baseline monitors from `stacks/uptime-kuma/bootstrap/monitors.yaml`
- creates or updates the `ops-board` status page

Run:

```bash
./scripts/bootstrap-uptime-kuma.sh
```

The script reads the username from `.env` and the password from `secrets/uptime_kuma_admin_password`. It never prints the password.

If Uptime Kuma is already initialized from a manual setup, the bootstrap cannot create a new first admin user. Set `UPTIME_KUMA_ADMIN_USERNAME` and `UPTIME_KUMA_ADMIN_PASSWORD_FILE` to match the existing local admin account, or reset the Uptime Kuma volume before using the first-run bootstrap path.

## smoke-day1.sh

Runs the repeatable Day-1 acceptance smoke after the board is running:

- validates the root Compose config
- re-runs the idempotent Uptime Kuma bootstrap
- checks Homepage, Uptime Kuma, the `ops-board` status page, SigNoz, the collector, and Plane
- optionally starts the onboarding dummy API and dummy job
- optionally checks recent SigNoz telemetry in ClickHouse

Run the full smoke:

```bash
./scripts/smoke-day1.sh
```

Run only the board checks:

```bash
./scripts/smoke-day1.sh --skip-onboarding
```

Run the onboarding endpoints without querying ClickHouse:

```bash
./scripts/smoke-day1.sh --skip-telemetry-query
```

The script does not create SigNoz or Plane admin accounts. Those first-run account steps remain manual for v1; use `docs/monitoring/first-run-accounts.md` for the checklist.

## status.sh

Shows Docker Compose status for one stack. It includes completed one-shot services such as init and migration jobs, and defaults to the root Ops Board aggregator:

```bash
./scripts/status.sh
```

Use `--stack` for isolated stack maintenance:

```bash
./scripts/status.sh --stack uptime-kuma
```

The script includes the root `.env` file automatically when it exists. It also includes stack-local env files when present:

- `stacks/<stack>/.env`
- `stacks/<stack>/<stack>.env`

Common stack names:

```bash
./scripts/status.sh --stack ops-board
./scripts/status.sh --stack signoz
./scripts/status.sh --stack uptime-kuma
./scripts/status.sh --stack homepage
./scripts/status.sh --stack plane
```

## update-stack.sh

Pulls images for a stack and runs `docker compose up -d`. It defaults to the root Ops Board aggregator:

```bash
./scripts/update-stack.sh
```

Use `--remove-orphans` only when you deliberately want Compose to remove containers that are no longer present in the compose file:

```bash
./scripts/update-stack.sh --stack signoz --remove-orphans
```

For stateful stacks, check the stack README before using this during a version upgrade.

The script includes the root `.env` file first, then stack-local env files when present. Stack-local values override root defaults.

Update a specific stack:

```bash
./scripts/update-stack.sh --stack ops-board
./scripts/update-stack.sh --stack uptime-kuma
./scripts/update-stack.sh --stack homepage
./scripts/update-stack.sh --stack plane
```

## backup.ps1

Creates a timestamped zip containing non-secret Ops Board config and docs:

- `.env.example`
- root `compose.yaml`
- stack Compose files
- Homepage YAML config
- Uptime Kuma monitor docs and bootstrap config
- Plane env example
- repo docs
- repo scripts

```powershell
.\scripts\backup.ps1
```

Use a custom local backup root:

```powershell
.\scripts\backup.ps1 -BackupRoot D:\ops-board-backups
```

The backup intentionally excludes `.env`, `secrets/*`, `stacks/plane/plane.env`, Docker volumes, and generated runtime data.

Restore reads the backup manifest and restores only entries that are still in the current allowlist. This keeps older config backups usable while still rejecting unsupported archive contents.

## restore.ps1

Restores allowlisted non-secret config and docs from a zip created by `backup.ps1`.

Smoke-test a restore into `temp/restore-smoke` without touching the repo root:

```powershell
$latest = Get-ChildItem D:\ops-board-backups -Filter "ops-board-config-*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
.\scripts\restore.ps1 -BackupPath $latest.FullName -TargetRoot temp\restore-smoke -Force
```

Restore into the repo root only when you intentionally want to overwrite allowlisted files:

```powershell
.\scripts\restore.ps1 -BackupPath <path-to-ops-board-config.zip> -Force
```

The restore script does not restore local secret files or Docker volume data.

## Direct Docker Compose Commands

Start Ops Board:

```bash
docker compose --env-file .env -f compose.yaml up -d
```

Start an individual stack outside the root aggregator:

```bash
docker compose --env-file .env -f stacks/signoz/compose.yaml up -d
```

Stop Ops Board while preserving volumes:

```bash
docker compose --env-file .env -f compose.yaml down
```

Reset Ops Board and wipe named volumes:

```bash
docker compose --env-file .env -f compose.yaml down -v
```

## PowerShell Compatibility

The transition PowerShell scripts mirror the older Windows workflow:

```powershell
.\scripts\init-local-config.ps1
.\scripts\bootstrap-uptime-kuma.ps1
.\scripts\smoke-day1.ps1
.\scripts\status.ps1
.\scripts\update-stack.ps1
```

Prefer the Linux scripts for new operator docs, examples, and deployment runs.

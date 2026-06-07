# Uptime Kuma Bootstrap Design

Date: 2026-06-07

## Purpose

Ops Board should not require manual Uptime Kuma setup during normal development. The repeatable path should initialize Uptime Kuma with the intended local database mode, create a demo/admin user from local secrets, create the `ops-board` status page, and create the baseline monitors from repo-owned config.

Manual UI setup should remain a fallback for unusual recovery cases, not the default day-1 workflow.

## Current Evidence

Uptime Kuma v2.3.2 supports database setup through environment variables. The upstream environment-variable docs list `UPTIME_KUMA_DB_TYPE` and Docker-secret-style `_FILE` variants for DB credentials, and the running container source confirms that `server/setup-database.js` skips the database wizard when `UPTIME_KUMA_DB_TYPE` is provided.

The running container source also confirms:

- `UPTIME_KUMA_ENABLE_EMBEDDED_MARIADB=1` enables the embedded MariaDB option.
- `embedded-mariadb` is accepted as an internal database type.
- The first admin user is created by the Socket.IO `setup` event.
- Monitors are created by the authenticated Socket.IO `add` event.
- Status pages are created by `addStatusPage` and updated by `saveStatusPage`.

No official admin-bootstrap environment variable was found in the current app source.

## Decision

Ops Board will bootstrap Uptime Kuma with two layers:

1. Compose/env for database selection.
2. A repo-owned bootstrap script for first user, monitors, and status page.

The bootstrap should call Uptime Kuma's app contract instead of writing directly to the database. Direct DB seeding is rejected because it couples Ops Board to Uptime Kuma's private schema and bypasses application validation.

## Configuration Contract

Add non-secret defaults to `.env.example`:

```dotenv
UPTIME_KUMA_DB_TYPE=embedded-mariadb
UPTIME_KUMA_ENABLE_EMBEDDED_MARIADB=1
UPTIME_KUMA_ADMIN_USERNAME=ops-board-demo
UPTIME_KUMA_ADMIN_PASSWORD_FILE=secrets/uptime_kuma_admin_password
UPTIME_KUMA_BOOTSTRAP_CONFIG=stacks/uptime-kuma/bootstrap/monitors.yaml
```

Add `secrets/uptime_kuma_admin_password` to the local secret set created by `scripts/init-local-config.ps1`.

For local development, the generated password can be demo-grade but must still live in `secrets/`, not in Git. For shared or production deployments, operators should replace it with a stronger secret before first startup.

## Bootstrap Script

Create `scripts/bootstrap-uptime-kuma.ps1`.

Responsibilities:

- Resolve repo root and load `.env`.
- Read `UPTIME_KUMA_ADMIN_PASSWORD_FILE` without printing the secret.
- Wait for Uptime Kuma at `UPTIME_KUMA_PUBLIC_URL`.
- Detect whether setup is needed by using the Socket.IO `needSetup` event.
- If setup is needed, call `setup(username, password)`.
- Log in through Socket.IO using the configured username/password.
- Read monitor definitions from `stacks/uptime-kuma/bootstrap/monitors.yaml`.
- Create missing monitors idempotently by name.
- Create `ops-board` status page if missing.
- Attach the baseline monitors to the status page with `saveStatusPage`.
- Leave existing extra monitors alone.

The script should be safe to run repeatedly. Re-running it should not duplicate monitors or rotate credentials.

## Monitor Configuration

Create `stacks/uptime-kuma/bootstrap/monitors.yaml` as the source of truth for the baseline:

```yaml
status_page:
  slug: ops-board
  title: Ops Board

monitors:
  - name: Homepage
    type: http
    url: http://host.docker.internal:3000
    accepted_statuscodes: ["200-299"]
  - name: Uptime Kuma
    type: http
    url: http://host.docker.internal:3001
    accepted_statuscodes: ["200-399"]
  - name: SigNoz UI
    type: http
    url: http://host.docker.internal:8080/api/v1/health
    accepted_statuscodes: ["200-299"]
  - name: SigNoz Collector
    type: http
    url: http://host.docker.internal:13133/
    accepted_statuscodes: ["200-299"]
  - name: Plane
    type: http
    url: http://host.docker.internal:8082
    accepted_statuscodes: ["200-399"]
  - name: Dummy API Health
    type: http
    url: http://host.docker.internal:18080/health
    accepted_statuscodes: ["200-299"]
    optional: true
```

The optional dummy API monitor is created inactive by default. Operators can resume it when the onboarding playground is running, or run the helper with `--skip-optional` to leave optional monitors out entirely.

## Helper Implementation Boundary

Use a small Python helper under `stacks/uptime-kuma/bootstrap/` for Socket.IO calls:

```text
stacks/uptime-kuma/bootstrap/
  monitors.yaml
  pyproject.toml
  bootstrap.py
  tests/
```

`scripts/bootstrap-uptime-kuma.ps1` remains the operator entrypoint. It runs the helper with `uv run --project stacks/uptime-kuma/bootstrap python bootstrap.py`.

The helper should use `uv`, `pydantic-settings`, `tenacity`, `PyYAML`, and `python-socketio`. This keeps it aligned with the repo's Python standards and avoids adding npm install/cache behavior for one bootstrap workflow.

The helper should not become a general Uptime Kuma SDK. It should implement only the calls Ops Board needs:

- `needSetup`
- `setup`
- `login`
- `getMonitorList`
- `add`
- `addStatusPage`
- `getStatusPage`
- `saveStatusPage`

If the Uptime Kuma Socket.IO contract changes in a future version, the helper should fail with a clear message and preserve existing data.

## Data Flow

```text
.env + secrets/
  -> scripts/init-local-config.ps1
      -> secrets/uptime_kuma_admin_password

.env + monitors.yaml
  -> scripts/bootstrap-uptime-kuma.ps1
      -> bootstrap.py
          -> Uptime Kuma Socket.IO
              -> user, monitors, status page
```

## Error Handling

The bootstrap should fail fast for missing config, missing password file, or failed Socket.IO responses.

Network waits should use bounded retry with backoff. If implemented in Python, use `tenacity`; if implemented in PowerShell/Node, use a small explicit retry loop with clear timeout messages.

The script must never print passwords or token values.

## Testing

Verification should include:

- Compose config validates with the new Uptime Kuma env values.
- `scripts/init-local-config.ps1` creates `secrets/uptime_kuma_admin_password` without printing the value.
- A disposable-volume smoke test proves `UPTIME_KUMA_DB_TYPE=embedded-mariadb` skips the database wizard.
- `scripts/bootstrap-uptime-kuma.ps1` creates the first user, baseline monitors, and `ops-board` status page on a clean Uptime Kuma volume.
- Re-running the bootstrap does not duplicate monitors.
- Current local board remains usable after the migration from manual setup to scripted bootstrap.

## Documentation Updates

Update these docs:

- `scripts/README.md`: document `bootstrap-uptime-kuma.ps1`.
- `stacks/uptime-kuma/docs/monitors.md`: state that monitors are now code-backed through `bootstrap/monitors.yaml`.
- `docs/monitoring/ops-board-user-manual.md`: replace manual Uptime Kuma setup language with bootstrap-first language and manual fallback notes.

## Out Of Scope

- Adding Healthchecks.
- Building a general-purpose Uptime Kuma SDK.
- Seeding Uptime Kuma by direct SQL writes.
- Automating SigNoz or Plane account creation in the same change.
- Storing demo credentials in tracked files.

## Acceptance Criteria

The bootstrap work is complete when a developer can run:

```powershell
.\scripts\init-local-config.ps1
docker compose --env-file .env -f compose.yaml up -d uptime-kuma
.\scripts\bootstrap-uptime-kuma.ps1
```

and then open:

```text
http://localhost:3001/dashboard
http://localhost:3001/status/ops-board
```

with the demo/admin user configured, baseline monitors visible, and the status page present.

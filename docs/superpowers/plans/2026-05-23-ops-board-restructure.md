# Ops Board Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the renamed `ops-board` repo from a single SigNoz repo into a Tailscale-first self-host operations control repo while preserving the verified SigNoz stack behavior.

**Architecture:** Keep each self-hosted application as an independent stack under `stacks/<stack-name>/`. Move the current SigNoz files into `stacks/signoz/` first, update relative bind mounts, then add root-level conventions and Tailscale access docs without adding reverse proxy services.

**Tech Stack:** Docker Compose, PowerShell, SigNoz, ClickHouse, ZooKeeper, Tailscale/MagicDNS, Markdown.

---

## File Structure

Create or modify these paths:

- Modify: `README.md` - root ops-board overview, repo layout, Tailscale-first model, stack commands.
- Modify: `HANDOFF.md` - mark the rename/reclone completed and point to the new layout.
- Create: `.env.example` - repo-wide non-secret defaults and documented placeholders.
- Create: `.gitignore` - ignore local env files, stack runtime data, backups, logs, and editor files.
- Create: `access/tailscale.md` - Tailscale/MagicDNS access model and SigNoz endpoints.
- Create: `scripts/backup.ps1` - placeholder script with clear no-op behavior.
- Create: `scripts/restore.ps1` - placeholder script with clear no-op behavior.
- Create: `scripts/update-stack.ps1` - reusable stack update helper.
- Create: `scripts/status.ps1` - stack status helper.
- Move: `docker/compose.yaml` to `stacks/signoz/compose.yaml`.
- Move: `docker/otel-collector-config.yaml` to `stacks/signoz/otel-collector-config.yaml`.
- Move: `common/` to `stacks/signoz/common/`.
- Move: `docs/ONBOARDING.md` to `stacks/signoz/docs/ONBOARDING.md`.
- Create: `stacks/signoz/README.md` - SigNoz-specific docs moved out of the root README.
- Remove: empty `docker/` and `docs/` folders after their contents move.

Out of scope for this plan:

- Adding Uptime Kuma.
- Adding Homepage.
- Adding Plane.
- Adding reverse proxy services.
- Changing SigNoz image versions.
- Changing Docker volume names.

---

### Task 1: Make Git Usable And Confirm Baseline

**Files:**
- No file changes.

- [ ] **Step 1: Trust the recloned repo path for Git**

Run:

```powershell
git config --global --add safe.directory D:/MyDocuments/03-PythonProjects/HU/ops-board
```

Expected: command exits with code `0` and prints no output.

- [ ] **Step 2: Confirm remote and clean tree**

Run:

```powershell
git remote -v
git status --short
```

Expected:

```text
origin  https://github.com/Wenjun-Mao/ops-board.git (fetch)
origin  https://github.com/Wenjun-Mao/ops-board.git (push)
```

`git status --short` may show only this plan file if it has not been committed yet:

```text
?? docs/superpowers/plans/2026-05-23-ops-board-restructure.md
```

- [ ] **Step 3: Confirm current SigNoz compose still renders before moving files**

Run:

```powershell
docker compose -p signoz -f docker/compose.yaml config --quiet
docker compose -p signoz -f docker/compose.yaml config --images
```

Expected images include these entries; order may vary:

```text
clickhouse/clickhouse-server:25.5.6
signoz/signoz:v0.125.1
signoz/signoz-otel-collector:v0.144.4
signoz/signoz-otel-collector:v0.144.4
clickhouse/clickhouse-server:25.5.6
signoz/zookeeper:3.7.1
```

- [ ] **Step 4: Commit the plan**

Run:

```powershell
git add docs/superpowers/plans/2026-05-23-ops-board-restructure.md
git commit -m "docs: plan ops-board restructure"
```

Expected: commit succeeds.

---

### Task 2: Move SigNoz Into `stacks/signoz`

**Files:**
- Move: `docker/compose.yaml` to `stacks/signoz/compose.yaml`
- Move: `docker/otel-collector-config.yaml` to `stacks/signoz/otel-collector-config.yaml`
- Move: `common/` to `stacks/signoz/common/`
- Move: `docs/ONBOARDING.md` to `stacks/signoz/docs/ONBOARDING.md`

- [ ] **Step 1: Stop the existing SigNoz containers without deleting volumes**

Run:

```powershell
docker compose -p signoz -f docker/compose.yaml down --remove-orphans
```

Expected: SigNoz containers are stopped and removed. Named volumes remain.

- [ ] **Step 2: Create target directories**

Run:

```powershell
New-Item -ItemType Directory -Force stacks\signoz\docs | Out-Null
```

Expected: command exits with code `0`.

- [ ] **Step 3: Move files with Git**

Run:

```powershell
git mv docker\compose.yaml stacks\signoz\compose.yaml
git mv docker\otel-collector-config.yaml stacks\signoz\otel-collector-config.yaml
git mv common stacks\signoz\common
git mv docs\ONBOARDING.md stacks\signoz\docs\ONBOARDING.md
```

Expected: files are moved and tracked as renames.

- [ ] **Step 4: Remove empty source folders if present**

Run:

```powershell
if (Test-Path docker) { Remove-Item docker -Force }
if (Test-Path docs) { Remove-Item docs -Force }
```

Expected: empty `docker/` and `docs/` folders are gone.

- [ ] **Step 5: Commit the file move before editing content**

Run:

```powershell
git add -A
git commit -m "chore: move signoz into stacks"
```

Expected: commit succeeds and contains only renames/removals from the move.

---

### Task 3: Update SigNoz Compose Paths

**Files:**
- Modify: `stacks/signoz/compose.yaml`

- [ ] **Step 1: Update ClickHouse bind mounts**

In `stacks/signoz/compose.yaml`, replace these mount paths:

```yaml
      - ../common/clickhouse/user_scripts:/var/lib/clickhouse/user_scripts/
      - ../common/clickhouse/config.xml:/etc/clickhouse-server/config.xml
      - ../common/clickhouse/users.xml:/etc/clickhouse-server/users.xml
      - ../common/clickhouse/custom-function.xml:/etc/clickhouse-server/custom-function.xml
      - ../common/clickhouse/user_scripts:/var/lib/clickhouse/user_scripts/
      - ../common/clickhouse/cluster.xml:/etc/clickhouse-server/config.d/cluster.xml
```

with:

```yaml
      - ./common/clickhouse/user_scripts:/var/lib/clickhouse/user_scripts/
      - ./common/clickhouse/config.xml:/etc/clickhouse-server/config.xml
      - ./common/clickhouse/users.xml:/etc/clickhouse-server/users.xml
      - ./common/clickhouse/custom-function.xml:/etc/clickhouse-server/custom-function.xml
      - ./common/clickhouse/user_scripts:/var/lib/clickhouse/user_scripts/
      - ./common/clickhouse/cluster.xml:/etc/clickhouse-server/config.d/cluster.xml
```

- [ ] **Step 2: Update collector config bind mount**

In `stacks/signoz/compose.yaml`, replace:

```yaml
      - ../common/signoz/otel-collector-opamp-config.yaml:/etc/manager-config.yaml
```

with:

```yaml
      - ./common/signoz/otel-collector-opamp-config.yaml:/etc/manager-config.yaml
```

Keep this line unchanged because the collector config stays beside the compose file:

```yaml
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
```

- [ ] **Step 3: Validate moved compose renders**

Run:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml config --quiet
docker compose -p signoz -f stacks/signoz/compose.yaml config --images
```

Expected images include these entries; order may vary:

```text
clickhouse/clickhouse-server:25.5.6
signoz/signoz:v0.125.1
signoz/signoz-otel-collector:v0.144.4
signoz/signoz-otel-collector:v0.144.4
clickhouse/clickhouse-server:25.5.6
signoz/zookeeper:3.7.1
```

- [ ] **Step 4: Commit compose path updates**

Run:

```powershell
git add stacks/signoz/compose.yaml
git commit -m "fix: update signoz stack paths"
```

Expected: commit succeeds.

---

### Task 4: Split Root README From SigNoz README

**Files:**
- Modify: `README.md`
- Create: `stacks/signoz/README.md`
- Modify: `stacks/signoz/docs/ONBOARDING.md`

- [ ] **Step 1: Replace root README with ops-board overview**

Replace `README.md` with:

```markdown
# Ops Board

Self-hosted operations board for monitoring and managing projects across local machines, VPSs, countries, and cloud providers.

The repo is organized as independent Docker Compose stacks. Tailscale is the first access layer; public reverse proxy services are intentionally deferred.

## Stacks

| Stack | Purpose | Status |
|-------|---------|--------|
| SigNoz | Central observability for logs, traces, metrics, and telemetry ingestion | Active |
| Uptime Kuma | Uptime and endpoint monitoring | Planned |
| Homepage | Private dashboard and service directory | Planned |
| Plane | Project and kanban management | Planned |
| Healthchecks | Scheduled job monitoring | Optional |

## Layout

```text
ops-board/
  README.md
  HANDOFF.md
  .env.example
  .gitignore

  access/
    tailscale.md

  scripts/
    backup.ps1
    restore.ps1
    status.ps1
    update-stack.ps1

  stacks/
    signoz/
      compose.yaml
      otel-collector-config.yaml
      common/
      docs/
      README.md
```

## Quick Start

Start SigNoz:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml up -d --remove-orphans
```

Open the SigNoz UI:

```text
http://localhost:8080
```

If this host is joined to Tailscale, use the host's MagicDNS name from other tailnet devices:

```text
http://<tailscale-hostname>:8080
```

## Access Model

Tailscale is the private network boundary for now.

- Do not add Caddy, Traefik, or nginx yet.
- Keep stack ports bound explicitly for local and tailnet access.
- Use Tailscale MagicDNS names in docs and future dashboards.

See `access/tailscale.md` for the current endpoint conventions.

## Stack Commands

Show stack status:

```powershell
.\scripts\status.ps1
```

Update a stack:

```powershell
.\scripts\update-stack.ps1 -Stack signoz
```

Stop SigNoz while preserving volumes:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml down
```

Reset SigNoz and wipe its named volumes:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml down -v
```

## Current Priorities

1. Keep SigNoz running from `stacks/signoz/`.
2. Document Tailscale access.
3. Add Uptime Kuma.
4. Add Homepage after monitored services have stable URLs.
5. Add backup/update automation before adding Plane.
```

- [ ] **Step 2: Create SigNoz-specific README**

Create `stacks/signoz/README.md` with:

```markdown
# SigNoz Stack

Shared SigNoz observability stack for centralized logs, traces, metrics, and OTLP ingestion across multiple projects.

## Quick Start

From the repo root:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml up -d --remove-orphans
```

Open UI:

```text
http://localhost:8080
```

From another device on the same Tailscale tailnet:

```text
http://<tailscale-hostname>:8080
```

## Current Stack Pins

| Component | Image |
|-----------|-------|
| SigNoz | `signoz/signoz:v0.125.1` |
| SigNoz OTel Collector | `signoz/signoz-otel-collector:v0.144.4` |
| ClickHouse | `clickhouse/clickhouse-server:25.5.6` |
| ZooKeeper | `signoz/zookeeper:3.7.1` |

ClickHouse stays at `25.5.6` because that is the version currently pinned by the upstream SigNoz Docker Compose layout.

## Published Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 8080 | HTTP | SigNoz web dashboard |
| 4317 | gRPC | OTLP receiver |
| 4318 | HTTP | OTLP receiver |
| 13133 | HTTP | Collector health check |

## Tailscale Endpoints

Use the host's Tailscale MagicDNS name from other tailnet devices:

```text
http://<tailscale-hostname>:8080
http://<tailscale-hostname>:4318/v1/logs
<tailscale-hostname>:4317
http://<tailscale-hostname>:13133/
```

## Restricted Network Setup

If the host cannot reach GitHub, pre-seed the ClickHouse init binary tarball locally.

1. Download the correct archive on a machine with internet:
   - `histogram-quantile_linux_amd64.tar.gz` for `x86_64/amd64`
   - `histogram-quantile_linux_arm64.tar.gz` for `aarch64/arm64`
2. Copy and rename it to:
   - `stacks/signoz/common/clickhouse/user_scripts/histogram-quantile.tar.gz`
3. Start stack:
   - `docker compose -p signoz -f stacks/signoz/compose.yaml up -d --remove-orphans`
4. Verify init succeeded:
   - `docker logs signoz-init-clickhouse --tail 100`
   - `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"`

Optional: if you have an accessible mirror URL, set `HISTOGRAM_QUANTILE_URL` in `stacks/signoz/.env`.

## Onboarding Projects

See `docs/ONBOARDING.md`.

## Stop And Reset

Stop while keeping data:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml down
```

Full reset:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml down -v
```
```

- [ ] **Step 3: Update SigNoz onboarding command and access wording**

In `stacks/signoz/docs/ONBOARDING.md`, replace:

```text
Remote / VPS (via nginx + SSL): `https://<domain>/v1/logs`
```

with:

```text
Remote / VPS over Tailscale: `http://<tailscale-hostname>:4318/v1/logs`
```

Replace:

```text
docker compose -p signoz -f docker/compose.yaml up -d --remove-orphans
```

with:

```text
docker compose -p signoz -f stacks/signoz/compose.yaml up -d --remove-orphans
```

Replace:

```text
Remote / VPS (nginx + SSL): `https://<domain>/v1/logs`
```

with:

```text
Remote / VPS over Tailscale: `http://<tailscale-hostname>:4318/v1/logs`
```

- [ ] **Step 4: Validate docs contain no old compose path**

Run:

```powershell
rg -n "docker/compose.yaml|nginx|reverse proxy|reverse-proxied|<domain>" README.md stacks/signoz
```

Expected: no matches for `docker/compose.yaml`. Any remaining `nginx`, `reverse proxy`, or `<domain>` matches must be explicitly described as deferred, not current setup.

- [ ] **Step 5: Commit README split**

Run:

```powershell
git add README.md stacks/signoz/README.md stacks/signoz/docs/ONBOARDING.md
git commit -m "docs: split ops-board and signoz docs"
```

Expected: commit succeeds.

---

### Task 5: Add Root Conventions

**Files:**
- Create: `.env.example`
- Create: `.gitignore`
- Create: `access/tailscale.md`

- [ ] **Step 1: Create `.env.example`**

Create `.env.example` with:

```dotenv
# Ops Board shared defaults
OPS_BOARD_TIMEZONE=America/Toronto
OPS_BOARD_TAILSCALE_HOSTNAME=your-hostname
OPS_BOARD_BACKUP_ROOT=D:\ops-board-backups

# SigNoz
SIGNOZ_HTTP_PORT=8080
SIGNOZ_OTLP_GRPC_PORT=4317
SIGNOZ_OTLP_HTTP_PORT=4318
SIGNOZ_COLLECTOR_HEALTH_PORT=13133
```

- [ ] **Step 2: Create `.gitignore`**

Create `.gitignore` with:

```gitignore
# Local environment files
.env
.env.*
!.env.example

# Runtime data and bind-mounted service state
data/
**/data/
**/runtime/
**/outputs/

# Backups and archives
backups/
*.bak
*.backup
*.dump
*.sql
*.tar
*.tar.gz
*.zip

# Logs
*.log
logs/
**/logs/

# OS/editor files
.DS_Store
Thumbs.db
.idea/
.vscode/
```

- [ ] **Step 3: Create Tailscale access doc**

Create `access/tailscale.md` with:

```markdown
# Tailscale Access

Ops Board uses Tailscale as the first private access layer.

Reverse proxy services are intentionally not part of the current architecture. Services are reached by port through the host's Tailscale IP or MagicDNS name.

## Host Naming

Use the Tailscale MagicDNS hostname for service URLs:

```text
<tailscale-hostname>
```

Set the same hostname in local `.env` files as:

```dotenv
OPS_BOARD_TAILSCALE_HOSTNAME=<tailscale-hostname>
```

## SigNoz

| Endpoint | URL |
|----------|-----|
| UI | `http://<tailscale-hostname>:8080` |
| OTLP HTTP logs | `http://<tailscale-hostname>:4318/v1/logs` |
| OTLP HTTP traces | `http://<tailscale-hostname>:4318/v1/traces` |
| OTLP HTTP metrics | `http://<tailscale-hostname>:4318/v1/metrics` |
| OTLP gRPC | `<tailscale-hostname>:4317` |
| Collector health | `http://<tailscale-hostname>:13133/` |

## Project Agents

Projects should send telemetry to the SigNoz host over Tailscale when they are outside the host machine.

Vector example:

```dotenv
VECTOR_SIGNOZ_OTLP_HTTP_URI=http://<tailscale-hostname>:4318/v1/logs
VECTOR_PROJECT_NAME=<project-name>
VECTOR_DEPLOYMENT_ENV=prod
```

## Security Notes

- Join only trusted machines to the tailnet.
- Keep SigNoz account registration closed after the admin account is created.
- Do not expose the SigNoz ports publicly until a reverse proxy and authentication boundary are intentionally added.
```

- [ ] **Step 4: Commit root conventions**

Run:

```powershell
git add .env.example .gitignore access/tailscale.md
git commit -m "docs: add tailscale-first repo conventions"
```

Expected: commit succeeds.

---

### Task 6: Add Script Placeholders And Helpers

**Files:**
- Create: `scripts/status.ps1`
- Create: `scripts/update-stack.ps1`
- Create: `scripts/backup.ps1`
- Create: `scripts/restore.ps1`

- [ ] **Step 1: Create `scripts/status.ps1`**

Create `scripts/status.ps1` with:

```powershell
param(
    [string]$Stack = "signoz"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $repoRoot "stacks\$Stack\compose.yaml"

if (-not (Test-Path $composeFile)) {
    throw "Compose file not found for stack '$Stack': $composeFile"
}

docker compose -p $Stack -f $composeFile ps
```

- [ ] **Step 2: Create `scripts/update-stack.ps1`**

Create `scripts/update-stack.ps1` with:

```powershell
param(
    [string]$Stack = "signoz"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $repoRoot "stacks\$Stack\compose.yaml"

if (-not (Test-Path $composeFile)) {
    throw "Compose file not found for stack '$Stack': $composeFile"
}

docker compose -p $Stack -f $composeFile pull
docker compose -p $Stack -f $composeFile up -d --remove-orphans
docker compose -p $Stack -f $composeFile ps
```

- [ ] **Step 3: Create `scripts/backup.ps1`**

Create `scripts/backup.ps1` with:

```powershell
param(
    [string]$BackupRoot = "$env:USERPROFILE\ops-board-backups"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force $BackupRoot | Out-Null

Write-Host "Backup root: $BackupRoot"
Write-Host "No backup jobs are defined yet. Add stack-specific backup tasks before storing production data."
```

- [ ] **Step 4: Create `scripts/restore.ps1`**

Create `scripts/restore.ps1` with:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupPath)) {
    throw "Backup path does not exist: $BackupPath"
}

Write-Host "Restore source: $BackupPath"
Write-Host "No restore jobs are defined yet. Add stack-specific restore tasks before storing production data."
```

- [ ] **Step 5: Smoke-test scripts**

Run:

```powershell
.\scripts\status.ps1 -Stack signoz
.\scripts\backup.ps1
```

Expected:

- `status.ps1` prints the SigNoz Compose services if the stack is running, or a valid empty/stopped Compose table if it is stopped.
- `backup.ps1` creates the backup root and prints that no backup jobs are defined yet.

- [ ] **Step 6: Commit scripts**

Run:

```powershell
git add scripts
git commit -m "chore: add ops-board helper scripts"
```

Expected: commit succeeds.

---

### Task 7: Restart And Verify SigNoz From New Path

**Files:**
- No file changes unless verification finds a path issue.

- [ ] **Step 1: Start SigNoz from the new path**

Run:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml up -d --remove-orphans
```

Expected: services start without missing bind mount errors.

- [ ] **Step 2: Verify Compose status**

Run:

```powershell
docker compose -p signoz -f stacks/signoz/compose.yaml ps -a
```

Expected:

- `signoz` is `Up` and `healthy`.
- `signoz-clickhouse` is `Up` and `healthy`.
- `signoz-zookeeper-1` is `Up` and `healthy`.
- `signoz-otel-collector` is `Up`.
- `signoz-telemetrystore-migrator` is `Exited (0)`.
- `signoz-init-clickhouse` is `Exited (0)`.

- [ ] **Step 3: Verify HTTP health endpoints**

Run:

```powershell
Invoke-WebRequest -Uri http://localhost:8080/api/v1/health -UseBasicParsing -TimeoutSec 10 | Select-Object StatusCode,Content
Invoke-WebRequest -Uri http://localhost:13133/ -UseBasicParsing -TimeoutSec 10 | Select-Object StatusCode,Content
```

Expected:

```text
StatusCode Content
---------- -------
       200 {"status":"ok"}
       200 {"status":"Server available", ...}
```

- [ ] **Step 4: Verify ClickHouse databases**

Run:

```powershell
docker exec signoz-clickhouse clickhouse-client -q "SHOW DATABASES"
```

Expected includes:

```text
signoz_analytics
signoz_logs
signoz_metadata
signoz_meter
signoz_metrics
signoz_traces
```

- [ ] **Step 5: Verify no old compose path remains**

Run:

```powershell
rg -n "docker/compose.yaml|docker\\compose.yaml|../common|../common" .
```

Expected:

- No references to `docker/compose.yaml` or `docker\compose.yaml`.
- No active compose bind mounts using `../common`.
- Historical references inside this plan file are acceptable if they explain the move.

- [ ] **Step 6: Commit verification-only fixes if needed**

If any path fix was needed, run:

```powershell
git add -A
git commit -m "fix: complete signoz path migration"
```

Expected: commit succeeds only if files changed.

---

### Task 8: Final Review

**Files:**
- No planned file changes.

- [ ] **Step 1: Check git status**

Run:

```powershell
git status --short
```

Expected: no output.

- [ ] **Step 2: Show recent commits**

Run:

```powershell
git log --oneline -5
```

Expected: recent commits include:

```text
docs: plan ops-board restructure
chore: move signoz into stacks
fix: update signoz stack paths
docs: split ops-board and signoz docs
docs: add tailscale-first repo conventions
chore: add ops-board helper scripts
```

- [ ] **Step 3: Push changes**

Run:

```powershell
git push
```

Expected: push succeeds to `https://github.com/Wenjun-Mao/ops-board.git`.

---

## Self-Review

- Spec coverage: The plan covers repo ownership cleanup, moving SigNoz under `stacks/signoz/`, path updates, root docs/conventions, Tailscale docs, helper scripts, and verification.
- Placeholder scan: No implementation step contains unfinished placeholder instructions.
- Scope check: Uptime Kuma, Homepage, Plane, Healthchecks, and reverse proxy are intentionally out of scope for this first milestone.
- Path consistency: All post-move commands use `stacks/signoz/compose.yaml`.

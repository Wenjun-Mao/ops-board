# Ops Board Day 1 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ops Board day-1 operational by starting the full board, initializing first-run apps, making Uptime Kuma the v1 status source, cleaning Homepage as the launch board, and proving backup/restore plus telemetry smoke paths work.

**Architecture:** Keep the existing per-stack Compose files as the source of truth and the root `compose.yaml` as the `ops-board` aggregator. Uptime Kuma owns endpoint status for v1; the bootstrap script creates its local admin user, baseline monitors, and status page. Homepage stays a private launch board that links to tools and may display the Uptime Kuma status widget. Backup/restore scripts protect the repo's non-secret operational contract files, not local secrets or generated runtime data.

**Tech Stack:** Docker Compose, PowerShell, Homepage YAML config, Uptime Kuma Socket.IO bootstrap, SigNoz, Plane, Playwright CLI for screenshots, `uv`/`pytest` for onboarding verification.

---

## File Structure

- Create: `docs/adr/001-v1-status-source.md`
  - Records the v1 decision that Uptime Kuma is the status source and Homepage is the launch board.
- Modify: `.env.example`
  - Adds `DUMMY_API_PUBLIC_URL=http://localhost:18080` for Homepage's onboarding playground link.
- Modify: `stacks/homepage/compose.yaml`
  - Passes `HOMEPAGE_VAR_DUMMY_API_URL` into Homepage using the new `.env.example` value.
- Modify: `stacks/homepage/config/services.yaml`
  - Reorders the launch board around Observability, Project Management, and Onboarding Playground.
- Modify: `stacks/homepage/config/settings.yaml`
  - Adds the Onboarding Playground layout band while preserving the dark, clean board style.
- Modify: `stacks/homepage/config/bookmarks.yaml`
  - Keeps reference links focused on repo/docs/vendor docs.
- Modify: `stacks/uptime-kuma/docs/monitors.md`
  - Defines the baseline monitor contract and points to the code-backed bootstrap source of truth.
- Modify: `scripts/backup.ps1`
  - Creates a timestamped zip of allowlisted non-secret config and docs.
- Modify: `scripts/restore.ps1`
  - Restores only the same allowlisted files from a generated zip, with a safe smoke-test target root.
- Modify: `scripts/README.md`
  - Documents backup/restore behavior, exclusions, and smoke-test commands.
- Modify: `docs/monitoring/ops-board-user-manual.md`
  - Updates day-1 workflow notes after the board is initialized.
- Modify: `docs/monitoring/images/homepage-overview.png`
  - Replaces the Homepage screenshot after cleanup.
- Modify: `docs/monitoring/images/uptime-kuma-first-run.png`
  - Replaces with the configured Uptime Kuma status/monitor screenshot.
- Modify: `docs/monitoring/images/signoz-first-run.png`
  - Replaces with the initialized SigNoz view or login view if the authenticated dashboard cannot be captured.
- Modify: `docs/monitoring/images/plane-first-run.png`
  - Replaces with the initialized Plane workspace view or login view if the authenticated workspace cannot be captured.

Do not modify or commit: `temp/HANDOFF.md`, `.env`, `secrets/*`, `stacks/plane/plane.env`, Docker volumes, or generated runtime data.

---

### Task 1: Preflight Runtime Snapshot

**Files:**
- Read only: `temp/HANDOFF.md`
- Read only: `compose.yaml`
- Read only: `.env.example`
- Read only: `scripts/status.ps1`

- [ ] **Step 1: Confirm git is clean except intentional plan work**

Run:

```powershell
git status --short --branch
```

Expected before implementation begins:

```text
## main...origin/main
?? docs/superpowers/plans/2026-06-07-ops-board-day-1-hardening.md
```

If other files appear, inspect them with `git diff -- <path>` and do not overwrite unrelated user changes.

- [ ] **Step 2: Confirm local runtime config exists without printing secrets**

Run:

```powershell
.\scripts\init-local-config.ps1
```

Expected output includes these non-secret status lines:

```text
Keeping existing .env. Use -Force to recreate it from .env.example.
Keeping existing Docker secret: secrets/signoz_jwt_secret. Use -Force to rotate it.
Keeping existing Plane env: stacks/plane/plane.env. Use -Force to recreate it.
Local config is ready.
```

Fresh clones may say `Wrote local .env from .env.example` and `Wrote Docker secret: ...`; that is also healthy. Do not print the contents of `.env`, `secrets/*`, or `stacks/plane/plane.env`.

- [ ] **Step 3: Validate the root Compose aggregator**

Run:

```powershell
docker compose --env-file .env -f compose.yaml config --quiet
```

Expected: command exits `0` with no output.

- [ ] **Step 4: Record current Docker container state**

Run:

```powershell
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected: output may include exited SigNoz/Uptime/Homepage containers and running Plane containers from the previous session. Preserve volumes; do not run `docker compose down -v`.

---

### Task 2: Start Board And Verify Local Endpoints

**Files:**
- Read only: `compose.yaml`
- Read only: `scripts/status.ps1`
- Read only: `examples/onboarding/compose.yaml`

- [ ] **Step 1: Start the full board**

Run:

```powershell
docker compose --env-file .env -f compose.yaml up -d
```

Expected: Docker starts or reuses containers for SigNoz, Uptime Kuma, Homepage, and Plane without port binding failures.

- [ ] **Step 2: Check Compose status through the repo script**

Run:

```powershell
.\scripts\status.ps1
```

Expected: long-running services show `running` or `healthy`; one-shot init/migrator services may show `exited (0)`.

- [ ] **Step 3: Run local endpoint checks**

Run:

```powershell
$checks = @(
    @{ Name = "Homepage"; Uri = "http://localhost:3000"; Codes = @(200) },
    @{ Name = "Uptime Kuma"; Uri = "http://localhost:3001"; Codes = @(200, 302) },
    @{ Name = "SigNoz health"; Uri = "http://localhost:8080/api/v1/health"; Codes = @(200) },
    @{ Name = "SigNoz collector"; Uri = "http://localhost:13133/"; Codes = @(200) },
    @{ Name = "Plane"; Uri = "http://localhost:8082"; Codes = @(200, 302, 307, 308) }
)

foreach ($check in $checks) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $check.Uri -MaximumRedirection 0 -TimeoutSec 20 -ErrorAction Stop
        $statusCode = [int]$response.StatusCode
    }
    catch [Microsoft.PowerShell.Commands.HttpResponseException] {
        $statusCode = [int]$_.Exception.Response.StatusCode
    }

    if ($check.Codes -notcontains $statusCode) {
        throw "$($check.Name) returned HTTP $statusCode for $($check.Uri)"
    }

    Write-Host "$($check.Name): HTTP $statusCode"
}
```

Expected:

```text
Homepage: HTTP 200
Uptime Kuma: HTTP 200
SigNoz health: HTTP 200
SigNoz collector: HTTP 200
Plane: HTTP 200
```

Plane or Uptime Kuma may return one of the accepted redirect codes when first-run setup is incomplete.

- [ ] **Step 4: Start the dummy API only when validating onboarding monitor coverage**

Run:

```powershell
docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
Invoke-WebRequest -UseBasicParsing http://localhost:18080/health -TimeoutSec 20
```

Expected: the health request returns HTTP `200` and JSON containing `"status":"ok"`.

---

### Task 3: Record The V1 Status Source Decision

**Files:**
- Create: `docs/adr/001-v1-status-source.md`

- [ ] **Step 1: Create the ADR**

Write `docs/adr/001-v1-status-source.md` with exactly this content:

```markdown
# 001. V1 Status Source

Date: 2026-06-07

## Status

Accepted

## Context

Ops Board needs a clear day-1 answer for "is this service alive?" while the stack is still intentionally small. The board already includes Homepage, Uptime Kuma, SigNoz, and Plane. Healthchecks may be useful later, but adding it before Uptime Kuma has been used in real work would add another alerting surface without evidence that it is needed.

Homepage can display links and lightweight widgets, SigNoz can explain what happened inside services, and Plane can track follow-up work. None of those should become the first v1 owner for endpoint uptime.

## Decision

Uptime Kuma is the v1 status source for endpoint health and status pages.

Homepage remains the private launch board. It links to SigNoz, Uptime Kuma, Plane, Ops Board docs, and the onboarding playground. Homepage may show the Uptime Kuma status widget once the `ops-board` status page exists, but it should not become a parallel monitor configuration surface.

SigNoz remains the debugging and telemetry source. It is monitored by Uptime Kuma at both the UI health endpoint and the collector health endpoint.

Healthchecks is deferred until scheduled-job monitoring in real projects proves that Uptime Kuma's push/HTTP monitor model is insufficient.

## Consequences

- Uptime Kuma monitor setup is documented as a day-1 required step.
- Homepage cleanup should favor clear links and a single Uptime Kuma widget over duplicate direct status widgets.
- New project onboarding should first add an endpoint/job signal to Uptime Kuma and telemetry to SigNoz before adding more tooling.
- Local Uptime Kuma data becomes valuable after first-run setup; avoid `docker compose down -v` unless intentionally resetting the board.

## Guardrails

- Keep Uptime Kuma status page slug `ops-board` for v1.
- Do not add Caddy, Traefik, nginx, or a public reverse proxy as part of this decision.
- Do not add Healthchecks until a pilot project produces a concrete need that Uptime Kuma cannot handle cleanly.
```

- [ ] **Step 2: Verify ADR content exists**

Run:

```powershell
Test-Path docs\adr\001-v1-status-source.md
Select-String -Path docs\adr\001-v1-status-source.md -Pattern "Uptime Kuma is the v1 status source"
```

Expected: `Test-Path` prints `True`, and `Select-String` prints the decision line.

- [ ] **Step 3: Commit checkpoint after review**

Run only after the user agrees to commit:

```powershell
git add docs/adr/001-v1-status-source.md
git commit -m "docs: record v1 status source decision"
```

---

### Task 4: Expand The Uptime Kuma Monitor Contract

**Files:**
- Modify: `stacks/uptime-kuma/docs/monitors.md`
- Modify: `docs/monitoring/ops-board-user-manual.md`

- [ ] **Step 1: Replace `stacks/uptime-kuma/docs/monitors.md`**

Use this complete content:

````markdown
# Uptime Kuma Monitors

Uptime Kuma is the v1 status source for Ops Board endpoint health.

Create these monitors manually after first-account setup. Use `host.docker.internal` for same-host checks from the Uptime Kuma container. The compose file maps `host.docker.internal` through Docker's host gateway.

## Status Page

Create one public status page inside Uptime Kuma:

```text
Slug: ops-board
Title: Ops Board
```

Add the core monitors to this status page after each monitor is created.

## Core Ops Board Monitors

| Name | Type | URL | Expected |
|------|------|-----|----------|
| Homepage | HTTP(s) | `http://host.docker.internal:3000` | `200` |
| Uptime Kuma | HTTP(s) | `http://host.docker.internal:3001` | `200` or first-run redirect |
| SigNoz UI | HTTP(s) | `http://host.docker.internal:8080/api/v1/health` | `200` |
| SigNoz Collector | HTTP(s) | `http://host.docker.internal:13133/` | `200` |
| Plane | HTTP(s) | `http://host.docker.internal:8082` | `200`, `302`, `307`, or `308` |

## Onboarding Playground Monitor

Create this monitor when the dummy API is running:

| Name | Type | URL | Expected |
|------|------|-----|----------|
| Dummy API Health | HTTP(s) | `http://host.docker.internal:18080/health` | `200` |

If the dummy API is stopped, pause the monitor instead of treating the red status as an Ops Board failure.

## Setup Notes

- Use monitor names exactly as listed so screenshots, docs, and future automation refer to the same labels.
- Keep the `ops-board` status page slug; Homepage's Uptime Kuma widget reads this slug.
- Do not add Healthchecks for v1. Revisit that only after a real scheduled-job pilot shows Uptime Kuma is not enough.
````

- [ ] **Step 2: Update the user manual Uptime Kuma section**

In `docs/monitoring/ops-board-user-manual.md`, replace the current `### Uptime Kuma` paragraph with:

```markdown
### Uptime Kuma

Use Uptime Kuma for health status and status page checks. It is the v1 status source for Ops Board.

![Uptime Kuma first-run setup](images/uptime-kuma-first-run.png)

On a clean rebuild, Uptime Kuma starts at database selection and instance setup. After setup, create the `ops-board` status page and the baseline monitors from `stacks/uptime-kuma/docs/monitors.md`.
```

- [ ] **Step 3: Verify monitor docs include the full baseline**

Run:

```powershell
Select-String -Path stacks\uptime-kuma\docs\monitors.md -Pattern "Homepage","Uptime Kuma","SigNoz UI","SigNoz Collector","Plane","Dummy API Health"
```

Expected: each monitor name appears at least once.

- [ ] **Step 4: Commit checkpoint after review**

Run only after the user agrees to commit:

```powershell
git add stacks/uptime-kuma/docs/monitors.md docs/monitoring/ops-board-user-manual.md
git commit -m "docs: define ops board monitor baseline"
```

---

### Task 5: Clean Homepage As The Launch Board

**Files:**
- Modify: `.env.example`
- Modify: `stacks/homepage/compose.yaml`
- Modify: `stacks/homepage/config/services.yaml`
- Modify: `stacks/homepage/config/settings.yaml`
- Modify: `stacks/homepage/config/bookmarks.yaml`

- [ ] **Step 1: Add the onboarding playground URL to `.env.example`**

Append this block after the Plane URL settings:

```dotenv

# Onboarding playground
DUMMY_API_PUBLIC_URL=http://localhost:18080
```

- [ ] **Step 2: Pass the dummy API URL into Homepage**

In `stacks/homepage/compose.yaml`, add this environment entry under `HOMEPAGE_VAR_PLANE_URL`:

```yaml
      HOMEPAGE_VAR_DUMMY_API_URL: ${DUMMY_API_PUBLIC_URL:-http://localhost:18080}
```

- [ ] **Step 3: Replace `stacks/homepage/config/services.yaml`**

Use this complete content:

```yaml
- Observability:
    - Homepage:
        href: "{{HOMEPAGE_VAR_HOMEPAGE_URL}}"
        description: Private service directory
    - Uptime Kuma:
        href: "{{HOMEPAGE_VAR_UPTIME_KUMA_URL}}"
        description: Endpoint and status page monitoring
        widget:
          type: uptimekuma
          url: "{{HOMEPAGE_VAR_UPTIME_KUMA_URL}}"
          slug: "{{HOMEPAGE_VAR_UPTIME_KUMA_STATUS_SLUG}}"
    - SigNoz:
        href: "{{HOMEPAGE_VAR_SIGNOZ_URL}}"
        description: Logs, traces, metrics, and OTLP ingestion
        ping: "{{HOMEPAGE_VAR_SIGNOZ_URL}}/api/v1/health"

- Project Management:
    - Plane:
        href: "{{HOMEPAGE_VAR_PLANE_URL}}"
        description: Operational follow-up and project work

- Onboarding Playground:
    - Dummy API:
        href: "{{HOMEPAGE_VAR_DUMMY_API_URL}}"
        description: Sample FastAPI service for health and trace checks
        ping: "{{HOMEPAGE_VAR_DUMMY_API_URL}}/health"
    - Ops Board Docs:
        href: "https://github.com/Wenjun-Mao/ops-board/tree/main/docs"
        description: Monitoring and onboarding guides
```

- [ ] **Step 4: Update Homepage layout**

In `stacks/homepage/config/settings.yaml`, replace the `layout` block with:

```yaml
layout:
  Observability:
    style: row
    columns: 3
  Project Management:
    style: row
    columns: 3
  Onboarding Playground:
    style: row
    columns: 3
  References:
    style: row
    columns: 3
```

- [ ] **Step 5: Replace `stacks/homepage/config/bookmarks.yaml`**

Use this complete content:

```yaml
- References:
    - Ops Board Repository:
        - href: https://github.com/Wenjun-Mao/ops-board
          description: Source, docs, and stack configuration
    - SigNoz Docs:
        - href: https://signoz.io/docs/
          description: Observability docs
    - Uptime Kuma Docs:
        - href: https://github.com/louislam/uptime-kuma/wiki
          description: Monitor and status page docs
    - Homepage Docs:
        - href: https://gethomepage.dev/
          description: Dashboard docs
    - Plane Docs:
        - href: https://developers.plane.so/self-hosting/overview
          description: Self-hosting docs
```

- [ ] **Step 6: Validate Homepage YAML through Compose startup**

Run:

```powershell
docker compose --env-file .env -f compose.yaml up -d homepage
Start-Sleep -Seconds 5
docker logs homepage --tail 80
Invoke-WebRequest -UseBasicParsing http://localhost:3000 -TimeoutSec 20
```

Expected: Homepage logs do not report YAML parse errors, and the request returns HTTP `200`.

- [ ] **Step 7: Commit checkpoint after review**

Run only after the user agrees to commit:

```powershell
git add .env.example stacks/homepage/compose.yaml stacks/homepage/config/services.yaml stacks/homepage/config/settings.yaml stacks/homepage/config/bookmarks.yaml
git commit -m "feat: clean homepage launch board"
```

---

### Task 6: Implement Config Backup And Restore

**Files:**
- Modify: `scripts/backup.ps1`
- Modify: `scripts/restore.ps1`
- Modify: `scripts/README.md`

- [ ] **Step 1: Replace `scripts/backup.ps1`**

Use this complete content:

```powershell
param(
    [string]$BackupRoot = "$env:USERPROFILE\ops-board-backups"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupName = "ops-board-config-$timestamp"
$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) $backupName
$archivePath = Join-Path $BackupRoot "$backupName.zip"

$backupItems = @(
    ".env.example",
    "compose.yaml",
    "README.md",
    "access/tailscale.md",
    "scripts/README.md",
    "scripts/init-local-config.ps1",
    "scripts/status.ps1",
    "scripts/update-stack.ps1",
    "scripts/backup.ps1",
    "scripts/restore.ps1",
    "stacks/signoz/compose.yaml",
    "stacks/signoz/otel-collector-config.yaml",
    "stacks/uptime-kuma/compose.yaml",
    "stacks/uptime-kuma/docs/monitors.md",
    "stacks/homepage/compose.yaml",
    "stacks/homepage/config/services.yaml",
    "stacks/homepage/config/widgets.yaml",
    "stacks/homepage/config/settings.yaml",
    "stacks/homepage/config/bookmarks.yaml",
    "stacks/plane/compose.yaml",
    "stacks/plane/plane.env.example",
    "docs"
)

function Copy-BackupItem {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    $source = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Backup item does not exist: $RelativePath"
    }

    $destination = Join-Path $stagingRoot $RelativePath
    $destinationParent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

try {
    foreach ($item in $backupItems) {
        Copy-BackupItem -RelativePath $item
    }

    $manifestPath = Join-Path $stagingRoot "_manifest.txt"
    $backupItems | Set-Content -LiteralPath $manifestPath -Encoding ascii

    Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $archivePath -Force

    Write-Host "Backup root: $BackupRoot"
    Write-Host "Created backup: $archivePath"
    Write-Host "Included non-secret config and docs only."
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
```

- [ ] **Step 2: Replace `scripts/restore.ps1`**

Use this complete content:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,

    [string]$TargetRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),

    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $BackupPath)) {
    throw "Backup path does not exist: $BackupPath"
}

if ([System.IO.Path]::GetExtension($BackupPath) -ne ".zip") {
    throw "Restore only supports .zip archives created by scripts/backup.ps1"
}

$targetRootPath = if (Test-Path -LiteralPath $TargetRoot) {
    (Resolve-Path -LiteralPath $TargetRoot).Path
}
else {
    New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
    (Resolve-Path -LiteralPath $TargetRoot).Path
}

$restoreItems = @(
    ".env.example",
    "compose.yaml",
    "README.md",
    "access/tailscale.md",
    "scripts/README.md",
    "scripts/init-local-config.ps1",
    "scripts/status.ps1",
    "scripts/update-stack.ps1",
    "scripts/backup.ps1",
    "scripts/restore.ps1",
    "stacks/signoz/compose.yaml",
    "stacks/signoz/otel-collector-config.yaml",
    "stacks/uptime-kuma/compose.yaml",
    "stacks/uptime-kuma/docs/monitors.md",
    "stacks/homepage/compose.yaml",
    "stacks/homepage/config/services.yaml",
    "stacks/homepage/config/widgets.yaml",
    "stacks/homepage/config/settings.yaml",
    "stacks/homepage/config/bookmarks.yaml",
    "stacks/plane/compose.yaml",
    "stacks/plane/plane.env.example",
    "docs"
)

function Restore-AllowedItem {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,

        [Parameter(Mandatory = $true)]
        [string]$SourceRoot,

        [Parameter(Mandatory = $true)]
        [string]$DestinationRoot
    )

    $source = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Backup archive is missing expected item: $RelativePath"
    }

    $destination = Join-Path $DestinationRoot $RelativePath
    if ((Test-Path -LiteralPath $destination) -and (-not $Force)) {
        throw "Restore target already exists: $RelativePath. Re-run with -Force to overwrite allowlisted files."
    }

    $destinationParent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) "ops-board-restore-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

try {
    Expand-Archive -LiteralPath $BackupPath -DestinationPath $stagingRoot -Force

    $manifestPath = Join-Path $stagingRoot "_manifest.txt"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Backup archive is missing _manifest.txt"
    }

    foreach ($item in $restoreItems) {
        Restore-AllowedItem -RelativePath $item -SourceRoot $stagingRoot -DestinationRoot $targetRootPath
    }

    Write-Host "Restore source: $BackupPath"
    Write-Host "Restore target: $targetRootPath"
    Write-Host "Restored allowlisted non-secret config and docs only."
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
```

- [ ] **Step 3: Update `scripts/README.md` backup section**

Replace the current `## backup.ps1` and `## restore.ps1` sections with:

````markdown
## backup.ps1

Creates a timestamped zip containing non-secret Ops Board config and docs:

- `.env.example`
- root `compose.yaml`
- stack Compose files
- Homepage YAML config
- Uptime Kuma monitor docs
- Plane env example
- repo docs
- repo scripts

Run:

```powershell
.\scripts\backup.ps1
```

Use a custom local backup root:

```powershell
.\scripts\backup.ps1 -BackupRoot D:\ops-board-backups
```

The backup intentionally excludes `.env`, `secrets/*`, `stacks/plane/plane.env`, Docker volumes, and generated runtime data.

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
````

- [ ] **Step 4: Smoke-test backup and restore without touching secrets**

Run:

```powershell
$backupRoot = "temp\backup-smoke"
$restoreRoot = "temp\restore-smoke"
Remove-Item -LiteralPath $backupRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $restoreRoot -Recurse -Force -ErrorAction SilentlyContinue

.\scripts\backup.ps1 -BackupRoot $backupRoot
$latest = Get-ChildItem $backupRoot -Filter "ops-board-config-*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
.\scripts\restore.ps1 -BackupPath $latest.FullName -TargetRoot $restoreRoot -Force

Test-Path "$restoreRoot\compose.yaml"
Test-Path "$restoreRoot\docs"
Test-Path "$restoreRoot\.env"
Test-Path "$restoreRoot\secrets"
```

Expected:

```text
True
True
False
False
```

- [ ] **Step 5: Commit checkpoint after review**

Run only after the user agrees to commit:

```powershell
git add scripts/backup.ps1 scripts/restore.ps1 scripts/README.md
git commit -m "feat: add config backup and restore scripts"
```

---

### Task 7: Bootstrap Uptime Kuma And Complete First-Run App Setup

**Files:**
- Runtime only: `.env`
- Runtime only: `secrets/*`
- Runtime only: Docker volumes for SigNoz, Uptime Kuma, Homepage, and Plane

- [ ] **Step 1: Open first-run URLs**

Open:

```text
http://localhost:3000
http://localhost:3001
http://localhost:8080
http://localhost:8082
```

Expected:

- Homepage loads the launch board.
- Uptime Kuma shows first-run setup or the configured monitor dashboard.
- SigNoz shows first admin setup, login, or an initialized dashboard.
- Plane shows workspace setup, login, or an initialized workspace.

- [ ] **Step 2: Initialize accounts without writing credentials to repo**

In the browser:

```text
SigNoz: create or log into the local admin account.
    Uptime Kuma: run the repo bootstrap script.
    Plane: create or log into the local workspace.
```

Expected: each app reaches its normal authenticated landing view. Do not store passwords, API keys, recovery codes, or tokens in Markdown files.

- [ ] **Step 3: Bootstrap Uptime Kuma**

Run:

```powershell
.\scripts\bootstrap-uptime-kuma.ps1
```

Expected: the script creates the first local admin user when needed, logs in through Uptime Kuma's Socket.IO app contract, creates missing baseline monitors from `stacks/uptime-kuma/bootstrap/monitors.yaml`, and creates or updates the `ops-board` status page.

- [ ] **Step 4: Verify Uptime Kuma status page**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:3001/status/ops-board -TimeoutSec 20
```

Expected: the request returns HTTP `200`, and the dashboard shows the baseline monitors without duplicates after repeated bootstrap runs.

---

### Task 8: Capture Updated Screenshots

**Files:**
- Modify: `docs/monitoring/images/homepage-overview.png`
- Modify: `docs/monitoring/images/uptime-kuma-first-run.png`
- Modify: `docs/monitoring/images/signoz-first-run.png`
- Modify: `docs/monitoring/images/plane-first-run.png`

- [ ] **Step 1: Capture Homepage**

Run:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 2000 http://localhost:3000 docs/monitoring/images/homepage-overview.png
```

Expected: the screenshot shows Observability, Project Management, Onboarding Playground, and References.

- [ ] **Step 2: Capture Uptime Kuma status page**

Run:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 2000 http://localhost:3001/status/ops-board docs/monitoring/images/uptime-kuma-first-run.png
```

Expected: the screenshot shows the `Ops Board` status page with baseline monitors.

- [ ] **Step 3: Capture SigNoz**

Run:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 2000 http://localhost:8080 docs/monitoring/images/signoz-first-run.png
```

Expected: the screenshot shows SigNoz initialized, login, or setup state. If this captures a login page while the browser session is authenticated elsewhere, use the in-app browser screenshot workflow after logging in and save over the same file.

- [ ] **Step 4: Capture Plane**

Run:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 2000 http://localhost:8082 docs/monitoring/images/plane-first-run.png
```

Expected: the screenshot shows Plane initialized, login, or workspace setup state. If this captures a login page while the browser session is authenticated elsewhere, use the in-app browser screenshot workflow after logging in and save over the same file.

- [ ] **Step 5: Inspect generated images**

Run:

```powershell
Get-Item docs\monitoring\images\homepage-overview.png,docs\monitoring\images\uptime-kuma-first-run.png,docs\monitoring\images\signoz-first-run.png,docs\monitoring\images\plane-first-run.png | Select-Object Name,Length,LastWriteTime
```

Expected: all four files have non-zero length and current timestamps.

- [ ] **Step 6: Commit checkpoint after review**

Run only after the user agrees to commit:

```powershell
git add docs/monitoring/images/homepage-overview.png docs/monitoring/images/uptime-kuma-first-run.png docs/monitoring/images/signoz-first-run.png docs/monitoring/images/plane-first-run.png
git commit -m "docs: update day one dashboard screenshots"
```

---

### Task 9: Prove Telemetry And Final Verification

**Files:**
- Read only: `examples/onboarding/shared/ops_observe.py`
- Read only: `examples/onboarding/dummy-api/app.py`
- Read only: `examples/onboarding/dummy-job/job.py`
- Read only: `examples/onboarding/compose.yaml`

- [ ] **Step 1: Run onboarding tests**

Run:

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
```

Expected: all onboarding tests pass.

- [ ] **Step 2: Run the dummy API and job against SigNoz**

Run:

```powershell
docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
Invoke-WebRequest -UseBasicParsing http://localhost:18080/health -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:18080/work/demo -TimeoutSec 20
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

Expected:

- `/health` returns HTTP `200`.
- `/work/demo` returns HTTP `200`.
- `dummy-job` exits `0`.

- [ ] **Step 3: Query ClickHouse for recent telemetry**

Run:

```powershell
docker exec signoz-clickhouse clickhouse-client --query "SELECT serviceName, name, count() FROM signoz_traces.signoz_index_v3 WHERE timestamp >= now() - INTERVAL 30 MINUTE AND serviceName IN ('dummy-api','dummy-job') GROUP BY serviceName, name ORDER BY serviceName, name"
```

Expected output includes:

```text
dummy-api    dummy-api.work
dummy-api    dummy-api.expensive-lookup
dummy-job    dummy-job.run
dummy-job    dummy-job.process-record
```

- [ ] **Step 4: Re-run final static/runtime checks**

Run:

```powershell
docker compose --env-file .env -f compose.yaml config --quiet
.\scripts\status.ps1
.\scripts\backup.ps1 -BackupRoot temp\backup-final
```

Expected:

- Compose config exits `0`.
- Status script returns container status without throwing.
- Backup script creates a zip under `temp\backup-final`.

- [ ] **Step 5: Confirm no ignored runtime files are staged**

Run:

```powershell
git status --short --ignored
```

Expected tracked changes may include docs, Homepage config, scripts, and screenshots. Ignored files may include `temp/`, `.env`, `secrets/*`, `stacks/plane/plane.env`, and local backup zips. Do not stage ignored runtime files.

---

## Self-Review Checklist

- Spec coverage:
  - Full board startup: Task 2.
  - First-run SigNoz/Uptime Kuma/Plane setup: Task 7.
  - Uptime Kuma monitor baseline: Tasks 3, 4, and 7.
  - Homepage launch board cleanup: Task 5.
  - Screenshot refresh: Task 8.
  - Backup/restore scripts: Task 6.
  - Telemetry proof and final checks: Task 9.
- Placeholder scan:
  - No `TBD`, `TODO`, or unspecified "handle edge cases" steps remain.
  - Manual UI work has exact URLs, labels, slugs, and expected outcomes.
- Type/path consistency:
  - `DUMMY_API_PUBLIC_URL` maps to `HOMEPAGE_VAR_DUMMY_API_URL`.
  - Uptime Kuma status slug remains `ops-board`.
  - Dummy API host port remains `18080`.
  - `temp/HANDOFF.md`, `.env`, `secrets/*`, and `stacks/plane/plane.env` remain uncommitted.

---

## Execution Handoff

Plan complete. Execute with either:

1. **Subagent-Driven (recommended):** one fresh worker per task with review between tasks.
2. **Inline Execution:** execute tasks in this session using `superpowers:executing-plans`, with checkpoints after each task.

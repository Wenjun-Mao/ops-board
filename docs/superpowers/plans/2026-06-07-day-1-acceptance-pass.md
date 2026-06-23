# Day-1 Acceptance Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove a fresh Ops Board reset reaches a usable Day-1 state, then capture the reusable smoke workflow, screenshots, and docs that future runs should follow.

**Architecture:** Keep first-run setup code-backed where the repo has a stable contract: Uptime Kuma uses the committed bootstrap script and monitor YAML. SigNoz and Plane remain manual account/workspace setup for v1, while the repo verifies their service health, telemetry path, and UI reachability without storing credentials. Add one repo-level smoke script so Day-1 acceptance can be repeated after resets without copying long command blocks from chat.

**Tech Stack:** PowerShell, Docker Compose, Uptime Kuma bootstrap helper, SigNoz ClickHouse query, onboarding dummy API/job, Playwright screenshot CLI, Markdown docs, ADRs.

---

## File Structure

- Create: `docs/adr/003-first-run-account-boundary.md`
  - Records that Uptime Kuma is automated, while SigNoz and Plane first admin/workspace setup stays manual for v1 unless a future ADR selects an official bootstrap contract.
- Create: `scripts/smoke-day1.ps1`
  - Runs the repeatable Day-1 acceptance smoke: Compose config, Uptime Kuma idempotent bootstrap, local endpoints, onboarding dummy API/job, and SigNoz telemetry query.
- Modify: `scripts/README.md`
  - Documents `smoke-day1.ps1`, when to run it, and what it intentionally does not automate.
- Modify: `scripts/backup.ps1`
  - Adds `scripts/smoke-day1.ps1` to the non-secret config backup allowlist.
- Modify: `scripts/restore.ps1`
  - Adds `scripts/smoke-day1.ps1` to the non-secret config restore allowlist.
- Modify: `docs/monitoring/ops-board-user-manual.md`
  - Adds a fresh local setup flow, a Day-1 acceptance smoke flow, and clearer first-run notes for SigNoz and Plane.
- Modify: `docs/monitoring/images/homepage-overview.png`
  - Refreshes Homepage screenshot after the clean reset.
- Modify: `docs/monitoring/images/uptime-kuma-first-run.png`
  - Refreshes Uptime Kuma to show the public `ops-board` status page produced by bootstrap.
- Modify: `docs/monitoring/images/signoz-first-run.png`
  - Refreshes SigNoz to show the current clean-reset first-run or login state. This may produce no Git diff if the current first-run state matches the existing image.
- Modify: `docs/monitoring/images/plane-first-run.png`
  - Refreshes Plane to show the current clean-reset first-run or login state. This may produce no Git diff if the current first-run state matches the existing image.
- Modify: `docs/monitoring/images/README.md`
  - Adds the exact screenshot capture commands.
- Modify: `.env.example`
  - Adds `UPTIME_KUMA_INTERNAL_URL` for container-internal Homepage widget access.
- Modify: `stacks/homepage/compose.yaml`
  - Splits Uptime Kuma public link and internal widget URL variables.
- Modify: `stacks/homepage/config/services.yaml`
  - Uses the public URL for the Uptime Kuma link and the internal URL for the Uptime Kuma widget.
- Modify: `docs/adr/001-v1-status-source.md`
  - Records the public-vs-internal URL rule for Homepage server-side widgets.

Do not commit or print: `.env`, `secrets/*`, `stacks/plane/plane.env`, `temp/*`, virtualenvs, caches, or Docker volume data.

---

### Task 1: Record The First-Run Account Boundary

**Files:**
- Create: `docs/adr/003-first-run-account-boundary.md`

- [ ] **Step 1: Create the ADR**

Create `docs/adr/003-first-run-account-boundary.md`:

```markdown
# 003. First-Run Account Boundary

Date: 2026-06-07

## Status

Accepted

## Context

Ops Board now has a repo-owned first-run bootstrap path for Uptime Kuma. That bootstrap uses Uptime Kuma's Socket.IO application contract, generated local secrets, and monitor definitions committed under `stacks/uptime-kuma/bootstrap/`.

SigNoz and Plane also have first-run account or workspace flows, but Ops Board has not selected a stable, documented bootstrap contract for those products. Their first-run data includes personal admin credentials, workspace names, and product-specific state. Seeding those databases directly would couple Ops Board to private schemas and bypass application validation.

## Decision

For v1, Ops Board automates Uptime Kuma first-run setup and keeps SigNoz and Plane first admin/workspace setup manual.

Repo-owned scripts may verify that SigNoz and Plane containers are healthy, that their UIs are reachable, and that SigNoz receives telemetry from the onboarding playground. Repo-owned scripts must not create SigNoz or Plane admin credentials, workspace users, or tokens unless a future ADR selects an official application-level bootstrap contract.

## Consequences

- A fresh local setup still has manual UI work for SigNoz and Plane accounts.
- Day-1 smoke verification can pass without storing SigNoz or Plane credentials in Git.
- Screenshots may show setup, login, or dashboard states depending on the local browser session and reset timing.
- Future automation for SigNoz or Plane needs its own ADR, secret contract, and regression tests.

## Guardrails

- Do not commit SigNoz, Plane, or Uptime Kuma passwords.
- Do not seed SigNoz or Plane databases directly for first-run setup.
- Keep generated local secrets in ignored files under `secrets/`.
- Keep manual account details in a password manager or another user-controlled secret store, not in repo docs.
```

- [ ] **Step 2: Verify the ADR exists and contains the decision**

Run:

```powershell
Test-Path docs\adr\003-first-run-account-boundary.md
Select-String -Path docs\adr\003-first-run-account-boundary.md -Pattern "keeps SigNoz and Plane first admin/workspace setup manual"
```

Expected:

```text
True
```

Then `Select-String` prints the decision line.

---

### Task 2: Add A Repeatable Day-1 Smoke Script

**Files:**
- Create: `scripts/smoke-day1.ps1`

- [ ] **Step 1: Run the red check before creating the script**

Run:

```powershell
.\scripts\smoke-day1.ps1 -Help
```

Expected: PowerShell reports that `scripts\smoke-day1.ps1` is not recognized or does not exist.

- [ ] **Step 2: Create `scripts/smoke-day1.ps1`**

Create `scripts/smoke-day1.ps1`:

```powershell
param(
    [switch]$SkipOnboarding,
    [switch]$SkipTelemetryQuery,
    [int]$TimeoutSec = 20
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Write-Section {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    Write-Host ""
    Write-Host "== $Name =="
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host $Label
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Test-HttpEndpoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [Parameter(Mandatory = $true)]
        [int[]]$AcceptedCodes
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -MaximumRedirection 0 -TimeoutSec $TimeoutSec -ErrorAction Stop
        $statusCode = [int]$response.StatusCode
    }
    catch [Microsoft.PowerShell.Commands.HttpResponseException] {
        $statusCode = [int]$_.Exception.Response.StatusCode
    }

    if ($AcceptedCodes -notcontains $statusCode) {
        throw "$Name returned HTTP $statusCode for $Uri"
    }

    Write-Host "$Name: HTTP $statusCode"
}

function Get-RecentTelemetry {
    $query = @"
SELECT serviceName, name, count()
FROM signoz_traces.signoz_index_v3
WHERE timestamp >= now() - INTERVAL 30 MINUTE
  AND serviceName IN ('dummy-api','dummy-job')
GROUP BY serviceName, name
ORDER BY serviceName, name
"@

    docker exec signoz-clickhouse clickhouse-client --query $query
    if ($LASTEXITCODE -ne 0) {
        throw "ClickHouse telemetry query failed with exit code $LASTEXITCODE"
    }
}

function Wait-RequiredTelemetry {
    $requiredPatterns = @(
        "dummy-api\s+dummy-api\.work",
        "dummy-api\s+dummy-api\.expensive-lookup",
        "dummy-job\s+dummy-job\.run",
        "dummy-job\s+dummy-job\.process-record"
    )

    $deadline = (Get-Date).AddSeconds(90)
    $lastOutput = ""

    do {
        $lastOutput = Get-RecentTelemetry | Out-String
        $missing = @(
            foreach ($pattern in $requiredPatterns) {
                if ($lastOutput -notmatch $pattern) {
                    $pattern
                }
            }
        )

        if ($missing.Count -eq 0) {
            Write-Host "Recent SigNoz telemetry:"
            Write-Host $lastOutput.Trim()
            return
        }

        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)

    Write-Host "Last telemetry query output:"
    Write-Host $lastOutput.Trim()
    throw "Timed out waiting for required dummy-api and dummy-job telemetry."
}

Push-Location $repoRoot
try {
    Write-Section "Compose"
    Invoke-CheckedCommand -Label "Validating root Compose config" -Command {
        docker compose --env-file .env -f compose.yaml config --quiet
    }

    Write-Section "Uptime Kuma Bootstrap"
    Invoke-CheckedCommand -Label "Running idempotent Uptime Kuma bootstrap" -Command {
        .\scripts\bootstrap-uptime-kuma.ps1
    }

    Write-Section "Local Endpoints"
    Test-HttpEndpoint -Name "Homepage" -Uri "http://localhost:3000" -AcceptedCodes @(200)
    Test-HttpEndpoint -Name "Uptime Kuma" -Uri "http://localhost:3001" -AcceptedCodes @(200, 302)
    Test-HttpEndpoint -Name "Uptime Kuma status page" -Uri "http://localhost:3001/status/ops-board" -AcceptedCodes @(200)
    Test-HttpEndpoint -Name "SigNoz health" -Uri "http://localhost:8080/api/v1/health" -AcceptedCodes @(200)
    Test-HttpEndpoint -Name "SigNoz collector" -Uri "http://localhost:13133/" -AcceptedCodes @(200)
    Test-HttpEndpoint -Name "Plane" -Uri "http://localhost:8082" -AcceptedCodes @(200, 302, 307, 308)

    if (-not $SkipOnboarding) {
        Write-Section "Onboarding Playground"
        Invoke-CheckedCommand -Label "Starting dummy API" -Command {
            docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
        }
        Test-HttpEndpoint -Name "Dummy API health" -Uri "http://localhost:18080/health" -AcceptedCodes @(200)
        Test-HttpEndpoint -Name "Dummy API work" -Uri "http://localhost:18080/work/demo" -AcceptedCodes @(200)
        Invoke-CheckedCommand -Label "Running dummy job" -Command {
            docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
        }

        if (-not $SkipTelemetryQuery) {
            Write-Section "SigNoz Telemetry"
            Wait-RequiredTelemetry
        }
    }

    Write-Host ""
    Write-Host "Day-1 smoke passed."
}
finally {
    Pop-Location
}
```

- [ ] **Step 3: Verify the script help path**

Run:

```powershell
Get-Command .\scripts\smoke-day1.ps1
```

Expected: PowerShell prints a command entry for `scripts\smoke-day1.ps1`.

- [ ] **Step 4: Run the smoke script without onboarding first**

Run:

```powershell
.\scripts\smoke-day1.ps1 -SkipOnboarding
```

Expected:

```text
== Compose ==
Validating root Compose config

== Uptime Kuma Bootstrap ==
Running idempotent Uptime Kuma bootstrap
Uptime Kuma admin setup already complete.
All configured monitors already exist.
Status page ready: /status/ops-board

== Local Endpoints ==
Homepage: HTTP 200
Uptime Kuma: HTTP 302
Uptime Kuma status page: HTTP 200
SigNoz health: HTTP 200
SigNoz collector: HTTP 200
Plane: HTTP 200

Day-1 smoke passed.
```

Uptime Kuma may return HTTP `200` instead of `302` if the local browser/session state changes how the unauthenticated route responds. Both are accepted by the script.

- [ ] **Step 5: Run the full smoke script**

Run:

```powershell
.\scripts\smoke-day1.ps1
```

Expected:

- Compose config validates.
- Uptime Kuma bootstrap reports existing setup and no duplicate monitors.
- Homepage, Uptime Kuma status page, SigNoz health, SigNoz collector, Plane, Dummy API health, and Dummy API work all return accepted HTTP statuses.
- Dummy job exits `0`.
- SigNoz ClickHouse query output contains:

```text
dummy-api    dummy-api.work
dummy-api    dummy-api.expensive-lookup
dummy-job    dummy-job.run
dummy-job    dummy-job.process-record
```

- [ ] **Step 6: If the full smoke fails, do root-cause debugging before patching**

Use `superpowers:systematic-debugging` before changing code.

Collect this evidence:

```powershell
.\scripts\status.ps1
docker logs uptime-kuma --tail 80
docker logs signoz --tail 80
docker logs signoz-otel-collector --tail 80
docker logs ops-board-dummy-api --tail 80
docker exec signoz-clickhouse clickhouse-client --query "SELECT count() FROM signoz_traces.signoz_index_v3 WHERE timestamp >= now() - INTERVAL 30 MINUTE"
```

Expected: the evidence identifies which layer failed: container health, HTTP endpoint, dummy app, collector ingestion, or ClickHouse query.

---

### Task 3: Add The Smoke Script To Backup And Restore

**Files:**
- Modify: `scripts/backup.ps1`
- Modify: `scripts/restore.ps1`

- [ ] **Step 1: Update the backup allowlist**

In `scripts/backup.ps1`, add this entry immediately after `"scripts/bootstrap-uptime-kuma.ps1",`:

```powershell
    "scripts/smoke-day1.ps1",
```

- [ ] **Step 2: Update the restore allowlist**

In `scripts/restore.ps1`, add this entry immediately after `"scripts/bootstrap-uptime-kuma.ps1",`:

```powershell
    "scripts/smoke-day1.ps1",
```

- [ ] **Step 3: Verify both allowlists include the smoke script**

Run:

```powershell
Select-String -Path scripts\backup.ps1,scripts\restore.ps1 -Pattern "scripts/smoke-day1.ps1"
```

Expected: one match in `scripts\backup.ps1` and one match in `scripts\restore.ps1`.

---

### Task 4: Document The Smoke Script

**Files:**
- Modify: `scripts/README.md`

- [ ] **Step 1: Add a `smoke-day1.ps1` section**

In `scripts/README.md`, add this section after `bootstrap-uptime-kuma.ps1`:

````markdown
## smoke-day1.ps1

Runs the repeatable Day-1 acceptance smoke after the board is running:

- validates the root Compose config
- re-runs the idempotent Uptime Kuma bootstrap
- checks Homepage, Uptime Kuma, the `ops-board` status page, SigNoz, the collector, and Plane
- optionally starts the onboarding dummy API and dummy job
- optionally checks recent SigNoz telemetry in ClickHouse

Run the full smoke:

```powershell
.\scripts\smoke-day1.ps1
```

Run only the board checks:

```powershell
.\scripts\smoke-day1.ps1 -SkipOnboarding
```

Run the onboarding endpoints without querying ClickHouse:

```powershell
.\scripts\smoke-day1.ps1 -SkipTelemetryQuery
```

The script does not create SigNoz or Plane admin accounts. Those first-run account steps remain manual for v1.
````

- [ ] **Step 2: Verify README references the script**

Run:

```powershell
Select-String -Path scripts\README.md -Pattern "smoke-day1.ps1","Day-1 acceptance smoke","does not create SigNoz or Plane admin accounts"
```

Expected: all three strings are found.

---

### Task 5: Update The User Manual For Fresh Setup And Acceptance

**Files:**
- Modify: `docs/monitoring/ops-board-user-manual.md`

- [ ] **Step 1: Add a fresh local setup section**

In `docs/monitoring/ops-board-user-manual.md`, add this section after `## Where To Start`:

````markdown
## Fresh Local Setup

From a clean checkout or after an intentional reset:

```powershell
.\scripts\init-local-config.ps1
docker compose --env-file .env -f compose.yaml up -d
.\scripts\bootstrap-uptime-kuma.ps1
.\scripts\smoke-day1.ps1 -SkipOnboarding
```

Use `.\scripts\init-local-config.ps1 -Force` only when intentionally recreating ignored local config and rotating local secrets.

Uptime Kuma is bootstrapped by code. SigNoz and Plane first admin/workspace setup remain manual for v1; keep those credentials outside the repo.
````

- [ ] **Step 2: Add a Day-1 acceptance smoke section**

In `docs/monitoring/ops-board-user-manual.md`, add this section after `## Current Local Endpoints`:

````markdown
## Day-1 Acceptance Smoke

Run the full smoke after the board is up:

```powershell
.\scripts\smoke-day1.ps1
```

The smoke verifies the board endpoints, the Uptime Kuma status page, the onboarding dummy API/job, and recent SigNoz telemetry for `dummy-api` and `dummy-job`.

If you only need to check the board and skip the onboarding playground:

```powershell
.\scripts\smoke-day1.ps1 -SkipOnboarding
```
````

- [ ] **Step 3: Tighten the dashboard notes**

Replace the paragraph under `### Homepage` that currently says:

```markdown
The local first-run view may show an Uptime Kuma widget error until Uptime Kuma is initialized and its widget/API settings are configured.
```

with:

```markdown
After `.\scripts\bootstrap-uptime-kuma.ps1` runs, Homepage should link to the Uptime Kuma dashboard and may show the `ops-board` status widget if the widget API is reachable.
```

Replace the SigNoz first-run paragraph with:

```markdown
On a clean rebuild, SigNoz may show first admin setup or login. The Day-1 smoke does not need SigNoz UI credentials; it verifies telemetry by sending dummy API/job spans and querying ClickHouse.
```

Replace the Plane first-run paragraph with:

```markdown
On a clean rebuild, Plane may show workspace setup or login. Create the Ops Board workspace manually when you are ready to track real operational follow-up; do not store Plane credentials in repo files.
```

- [ ] **Step 4: Update the V1 limits**

Replace the `Current manual steps:` list with:

```markdown
Current manual steps:

- Create SigNoz and Plane first admin/workspace accounts through their UIs.
- Capture authenticated screenshots manually when the browser session matters.
- Add real project entries to Homepage manually.
- Use project docs to track ownership and runtime location.
```

- [ ] **Step 5: Verify the manual references the new workflow**

Run:

```powershell
Select-String -Path docs\monitoring\ops-board-user-manual.md -Pattern "Fresh Local Setup","Day-1 Acceptance Smoke","smoke-day1.ps1","SigNoz and Plane first admin/workspace setup remain manual"
```

Expected: all four strings are found.

---

### Task 6: Refresh Monitoring Screenshots

**Files:**
- Modify: `docs/monitoring/images/homepage-overview.png`
- Modify: `docs/monitoring/images/uptime-kuma-first-run.png`
- Modify: `docs/monitoring/images/signoz-first-run.png`
- Modify: `docs/monitoring/images/plane-first-run.png`
- Modify: `docs/monitoring/images/README.md`

- [ ] **Step 1: Verify screenshot tooling**

Run:

```powershell
npx playwright --version
```

Expected: Playwright prints a version string. If this command fails because Playwright browsers are not installed, run:

```powershell
npx playwright install chromium
```

Expected: Chromium browser installation completes without errors.

- [ ] **Step 2: Capture Homepage**

Run:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:3000 docs/monitoring/images/homepage-overview.png
```

Expected: `docs/monitoring/images/homepage-overview.png` is overwritten with a non-empty screenshot of the launch board.

- [ ] **Step 3: Capture Uptime Kuma status page**

Run:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:3001/status/ops-board docs/monitoring/images/uptime-kuma-first-run.png
```

Expected: `docs/monitoring/images/uptime-kuma-first-run.png` is overwritten with a non-empty screenshot of the `Ops Board` status page.

- [ ] **Step 4: Capture SigNoz**

Run:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:8080 docs/monitoring/images/signoz-first-run.png
```

Expected: `docs/monitoring/images/signoz-first-run.png` is overwritten with a non-empty screenshot of the current SigNoz first-run, login, or dashboard state.

- [ ] **Step 5: Capture Plane**

Run:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:8082 docs/monitoring/images/plane-first-run.png
```

Expected: `docs/monitoring/images/plane-first-run.png` is overwritten with a non-empty screenshot of the current Plane first-run, login, or workspace state.

- [ ] **Step 6: Inspect screenshot file sizes**

Run:

```powershell
Get-Item docs\monitoring\images\homepage-overview.png,docs\monitoring\images\uptime-kuma-first-run.png,docs\monitoring\images\signoz-first-run.png,docs\monitoring\images\plane-first-run.png | Select-Object Name,Length,LastWriteTime
```

Expected: all four files have non-zero `Length` and current `LastWriteTime` values.

- [ ] **Step 7: Update image README**

Replace `docs/monitoring/images/README.md` with:

````markdown
# Monitoring Images

These screenshots support `docs/monitoring/ops-board-user-manual.md`.

Capture them from the repo root after the board is running:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:3000 docs/monitoring/images/homepage-overview.png
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:3001/status/ops-board docs/monitoring/images/uptime-kuma-first-run.png
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:8080 docs/monitoring/images/signoz-first-run.png
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:8082 docs/monitoring/images/plane-first-run.png
```

SigNoz and Plane screenshots may show setup, login, or dashboard states depending on whether the local runtime has been initialized. Do not commit screenshots that expose credentials, tokens, or private project data.
````

- [ ] **Step 8: Visually inspect screenshots**

Use `view_image` or open the files locally:

```powershell
Get-Item docs\monitoring\images\*.png | Select-Object Name,Length
```

Expected:

- Homepage screenshot shows Observability, Project Management, Onboarding Playground, and References.
- Uptime Kuma screenshot shows the public `Ops Board` status page.
- SigNoz screenshot shows a normal first-run, login, or dashboard view without credentials.
- Plane screenshot shows a normal first-run, login, or dashboard view without credentials.

- [ ] **Step 9: Fix Homepage Uptime Kuma widget API errors if present**

If `docs/monitoring/images/homepage-overview.png` shows a red `API Error` on the Uptime Kuma widget, inspect logs:

```powershell
docker logs homepage --tail 80
Invoke-WebRequest -UseBasicParsing http://localhost:3001/api/status-page/ops-board -TimeoutSec 20 | Select-Object StatusCode
```

Expected root cause when this bug appears:

```text
Homepage logs show it is calling http://localhost:3001/api/status-page/ops-board from inside the Homepage container and getting ECONNREFUSED.
The host request to http://localhost:3001/api/status-page/ops-board returns HTTP 200.
```

Apply this durable contract fix:

In `.env.example`, add after `UPTIME_KUMA_PUBLIC_URL=http://localhost:3001`:

```dotenv
UPTIME_KUMA_INTERNAL_URL=http://host.docker.internal:3001
```

In `stacks/homepage/compose.yaml`, replace:

```yaml
      HOMEPAGE_VAR_UPTIME_KUMA_URL: ${UPTIME_KUMA_PUBLIC_URL:-http://localhost:3001}
```

with:

```yaml
      HOMEPAGE_VAR_UPTIME_KUMA_PUBLIC_URL: ${UPTIME_KUMA_PUBLIC_URL:-http://localhost:3001}
      HOMEPAGE_VAR_UPTIME_KUMA_INTERNAL_URL: ${UPTIME_KUMA_INTERNAL_URL:-http://host.docker.internal:3001}
```

In `stacks/homepage/config/services.yaml`, replace the Uptime Kuma service with:

```yaml
    - Uptime Kuma:
        href: "{{HOMEPAGE_VAR_UPTIME_KUMA_PUBLIC_URL}}"
        description: Endpoint and status page monitoring
        widget:
          type: uptimekuma
          url: "{{HOMEPAGE_VAR_UPTIME_KUMA_INTERNAL_URL}}"
          slug: "{{HOMEPAGE_VAR_UPTIME_KUMA_STATUS_SLUG}}"
```

In `docs/adr/001-v1-status-source.md`, add this paragraph after the Homepage decision paragraph:

```markdown
Homepage should use browser-facing public URLs for links and container-reachable internal URLs for server-side widgets. For Uptime Kuma, that means the link can use `UPTIME_KUMA_PUBLIC_URL`, while the widget proxy should use `UPTIME_KUMA_INTERNAL_URL`.
```

Restart Homepage and recapture the screenshot:

```powershell
docker compose --env-file .env -f compose.yaml up -d homepage
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:3000 docs/monitoring/images/homepage-overview.png
docker logs homepage --tail 80
```

Expected: the Homepage screenshot shows Uptime Kuma widget stats, and the fresh Homepage logs do not show Uptime Kuma `ECONNREFUSED` widget proxy errors.

---

### Task 7: Run Final Verification

**Files:**
- Runtime read/write only: Docker containers and volumes.
- Read only: repo scripts and tests.

- [ ] **Step 1: Run the new smoke script**

Run:

```powershell
.\scripts\smoke-day1.ps1
```

Expected: command exits `0` and prints `Day-1 smoke passed.`

- [ ] **Step 2: Run bootstrap tests**

Run:

```powershell
uv run --project stacks/uptime-kuma/bootstrap pytest stacks/uptime-kuma/bootstrap/tests -v
```

Expected: all bootstrap tests pass.

- [ ] **Step 3: Run onboarding tests**

Run:

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
```

Expected: all onboarding tests pass.

- [ ] **Step 4: Validate root Compose config**

Run:

```powershell
docker compose --env-file .env -f compose.yaml config --quiet
```

Expected: command exits `0`.

- [ ] **Step 5: Run backup/restore smoke**

Run:

```powershell
$backupRoot = "temp\backup-day1-acceptance-smoke"
$restoreRoot = "temp\restore-day1-acceptance-smoke"
Remove-Item -LiteralPath $backupRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $restoreRoot -Recurse -Force -ErrorAction SilentlyContinue
.\scripts\backup.ps1 -BackupRoot $backupRoot
$latest = Get-ChildItem $backupRoot -Filter "ops-board-config-*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
.\scripts\restore.ps1 -BackupPath $latest.FullName -TargetRoot $restoreRoot -Force
Test-Path "$restoreRoot\scripts\smoke-day1.ps1"
Test-Path "$restoreRoot\docs\monitoring\ops-board-user-manual.md"
Test-Path "$restoreRoot\secrets"
```

Expected:

```text
True
True
False
```

- [ ] **Step 6: Check git status**

Run:

```powershell
git status --short --ignored
```

Expected:

- Tracked changes include the ADR, smoke script, docs, and refreshed screenshots.
- Ignored local runtime files include `.env`, `secrets/*`, `temp/*`, virtualenvs, caches, `stacks/plane/plane.env`, and `stacks/uptime-kuma/bootstrap/uv.lock`.
- No ignored runtime files are staged.

---

### Task 8: Commit And Push

**Files:**
- All changed tracked files.

- [ ] **Step 1: Stage repo-owned changes**

Run:

```powershell
git add docs\adr\003-first-run-account-boundary.md docs\adr\001-v1-status-source.md .env.example scripts\smoke-day1.ps1 scripts\README.md scripts\backup.ps1 scripts\restore.ps1 stacks\homepage\compose.yaml stacks\homepage\config\services.yaml docs\monitoring\ops-board-user-manual.md docs\monitoring\images\README.md docs\monitoring\images\homepage-overview.png docs\monitoring\images\uptime-kuma-first-run.png docs\monitoring\images\signoz-first-run.png docs\monitoring\images\plane-first-run.png docs\superpowers\plans\2026-06-07-day-1-acceptance-pass.md
git diff --cached --name-only
```

Expected staged files:

```text
docs/adr/003-first-run-account-boundary.md
docs/adr/001-v1-status-source.md
.env.example
scripts/smoke-day1.ps1
scripts/README.md
scripts/backup.ps1
scripts/restore.ps1
stacks/homepage/compose.yaml
stacks/homepage/config/services.yaml
docs/monitoring/ops-board-user-manual.md
docs/monitoring/images/README.md
docs/monitoring/images/homepage-overview.png
docs/monitoring/images/uptime-kuma-first-run.png
docs/superpowers/plans/2026-06-07-day-1-acceptance-pass.md
```

`docs/monitoring/images/signoz-first-run.png` and `docs/monitoring/images/plane-first-run.png` may be absent from the staged diff if recapturing them produced byte-identical clean first-run images.

- [ ] **Step 2: Commit**

Run:

```powershell
git commit -m "docs: add day one acceptance smoke"
```

Expected: Git creates a commit.

- [ ] **Step 3: Push**

Run:

```powershell
git push origin main
```

Expected: `main` pushes to `origin/main`.

---

## Self-Review Checklist

- Spec coverage:
  - Clean board proof: Tasks 2 and 7.
  - Uptime Kuma idempotent bootstrap: Task 2 and Task 7.
  - SigNoz telemetry proof: Task 2 and Task 7.
  - SigNoz/Plane account boundary: Task 1 and Task 5.
  - Screenshots: Task 6.
  - Docs/runbook updates: Tasks 4, 5, and 6.
  - Backup/restore coverage: Task 3 and Task 7.
- Placeholder scan:
  - No banned marker tokens or vague implementation steps remain.
  - Credential handling is explicit: do not store or print local account secrets.
- Type/path consistency:
  - Smoke script path is `scripts/smoke-day1.ps1`.
  - Status page slug remains `ops-board`.
  - Dummy API host port remains `18080`.
  - ClickHouse container name remains `signoz-clickhouse`.
  - Plan path is `docs/superpowers/plans/2026-06-07-day-1-acceptance-pass.md`.

---

## Execution Handoff

Plan complete. Execute with either:

1. **Subagent-Driven (recommended):** one fresh worker per task with review between tasks.
2. **Inline Execution:** execute tasks in this session using `superpowers:executing-plans`, with checkpoints after each task.

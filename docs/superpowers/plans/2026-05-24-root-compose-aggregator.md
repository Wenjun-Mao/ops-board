# Root Compose Aggregator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a root `compose.yaml` that runs the existing per-stack Compose files as one `ops-board` Compose project while preserving the per-stack files as the source of truth.

**Architecture:** Keep `stacks/<stack>/compose.yaml` files independently runnable and add a thin root aggregator using Docker Compose `include`. The root project becomes the normal day-to-day lifecycle surface for the whole board, while per-stack commands remain available for isolated maintenance. Because this repo is still in development, the runtime migration uses a clean rebuild and intentionally deletes existing local stack volumes.

**Tech Stack:** Docker Compose v5 / Compose Specification `include`, PowerShell helper scripts, Markdown docs.

---

## Source Notes

- Docker Compose `include` requires Docker Compose 2.20.0+ and loads included Compose files with their own project directories so relative bind mounts keep working.
- Included resources are copied into the current Compose application model. The root `name: ops-board` becomes the project name for the aggregate model.
- Compose project names prefix unnamed volumes. SigNoz and Uptime Kuma already pin their volume names, but Plane currently uses unnamed volumes that become `plane_*` under the per-stack project and would become `ops-board_*` under the root project unless pinned.
- Existing individual stacks are currently running as separate projects. The migration intentionally stops those projects with `down -v` before starting the root project because this is still a development environment and the user has approved clearing existing data.

---

## File Structure

Create or modify these paths:

- Create: `compose.yaml` - root `ops-board` aggregator using `include`.
- Modify: `stacks/plane/compose.yaml` - pin Plane volume names to stack-specific `plane_*` names so future root and per-stack runs use predictable volume names.
- Modify: `scripts/init-local-config.ps1` - generate ignored `stacks/plane/plane.env` from secret files so the root aggregator works after a fresh clone.
- Modify: `scripts/status.ps1` - support `-Stack ops-board` and make it the default status target.
- Modify: `scripts/update-stack.ps1` - support `-Stack ops-board` and make it the default update target.
- Modify: `README.md` - document the root aggregator as the normal full-board workflow and document the clean rebuild from separate projects.
- Modify: `scripts/README.md` - document the new script default and root Compose commands.

Out of scope:

- Docker Swarm stacks or Kubernetes.
- Public reverse proxy or TLS.
- True nested stack UI in Docker Desktop; Compose still shows one flat project named `ops-board`.
- Profiles for partial startup; add profiles later only if full-board startup becomes awkward.

---

## Implementation Tasks

### Task 1: Pin Plane Volume Names For Predictable Future Runs

**Files:**
- Modify: `stacks/plane/compose.yaml`

- [ ] **Step 1: Replace the Plane `volumes:` block with explicit names**

Replace the final `volumes:` block in `stacks/plane/compose.yaml`:

```yaml
volumes:
  pgdata:
  redisdata:
  uploads:
  logs_api:
  logs_worker:
  logs_beat-worker:
  logs_migrator:
  rabbitmq_data:
  proxy_config:
  proxy_data:
```

with:

```yaml
volumes:
  pgdata:
    name: plane_pgdata
  redisdata:
    name: plane_redisdata
  uploads:
    name: plane_uploads
  logs_api:
    name: plane_logs_api
  logs_worker:
    name: plane_logs_worker
  logs_beat-worker:
    name: plane_logs_beat-worker
  logs_migrator:
    name: plane_logs_migrator
  rabbitmq_data:
    name: plane_rabbitmq_data
  proxy_config:
    name: plane_proxy_config
  proxy_data:
    name: plane_proxy_data
```

- [ ] **Step 2: Validate the standalone Plane config**

Run:

```powershell
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml config --quiet
```

Expected: exits `0`.

- [ ] **Step 3: Verify Plane volume names are stable**

Run:

```powershell
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml config | Select-String -Pattern "name: plane_(pgdata|redisdata|uploads|logs_api|logs_worker|logs_beat-worker|logs_migrator|rabbitmq_data|proxy_config|proxy_data)"
```

Expected: output contains all ten pinned Plane volume names.

- [ ] **Step 4: Commit Plane volume pinning**

```powershell
git add stacks/plane/compose.yaml
git commit -m "chore: pin plane volume names"
```

---

### Task 2: Add Root Ops Board Compose Aggregator

**Files:**
- Create: `compose.yaml`

- [ ] **Step 1: Create root `compose.yaml`**

Create `compose.yaml` at the repo root:

```yaml
# Root Compose aggregator for the whole Ops Board.
# The included stack files remain the source of truth for service definitions.
name: ops-board

include:
  - path: stacks/signoz/compose.yaml
    env_file: .env
  - path: stacks/uptime-kuma/compose.yaml
    env_file: .env
  - path: stacks/homepage/compose.yaml
    env_file: .env
  - path: stacks/plane/compose.yaml
    env_file: stacks/plane/plane.env
```

- [ ] **Step 2: Validate the root aggregate config**

Run:

```powershell
docker compose --env-file .env -f compose.yaml config --quiet
```

Expected: exits `0`.

- [ ] **Step 3: Verify the root aggregate project name and service list**

Run:

```powershell
docker compose --env-file .env -f compose.yaml config --services
```

Expected output includes:

```text
init-clickhouse
zookeeper-1
clickhouse
signoz
otel-collector
signoz-telemetrystore-migrator
uptime-kuma
homepage
web
space
admin
live
api
worker
beat-worker
migrator
plane-db
plane-redis
plane-mq
plane-minio
proxy
```

Run:

```powershell
docker compose --env-file .env -f compose.yaml config | Select-String -Pattern "^name: ops-board"
```

Expected: output contains `name: ops-board`.

- [ ] **Step 4: Verify the root aggregate reuses Plane's pinned volumes**

Run:

```powershell
docker compose --env-file .env -f compose.yaml config | Select-String -Pattern "name: plane_(pgdata|redisdata|uploads|logs_api|logs_worker|logs_beat-worker|logs_migrator|rabbitmq_data|proxy_config|proxy_data)"
```

Expected: output contains all ten pinned Plane volume names and no `ops-board_pgdata` line.

- [ ] **Step 5: Commit the root aggregator**

```powershell
git add compose.yaml
git commit -m "feat: add ops-board compose aggregator"
```

---

### Task 3: Make Local Config Bootstrap Root-Ready

**Files:**
- Modify: `scripts/init-local-config.ps1`

- [ ] **Step 1: Add Plane env paths**

Add these variables after the Plane secret file variables:

```powershell
$planeStackDir = Join-Path $repoRoot "stacks\plane"
$planeEnvExample = Join-Path $planeStackDir "plane.env.example"
$planeEnvFile = Join-Path $planeStackDir "plane.env"
```

- [ ] **Step 2: Add env file helpers**

Add these functions after `Set-SecretFile`:

```powershell
function Set-EnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$Lines,

        [Parameter(Mandatory = $true)]
        [string]$Key,

        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $found = $false
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index] -match "^$([regex]::Escape($Key))=") {
            $Lines[$index] = "$Key=$Value"
            $found = $true
            break
        }
    }

    if (-not $found) {
        $Lines.Add("$Key=$Value")
    }
}

function Get-SecretText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return (Get-Content -Raw -LiteralPath $Path).Trim()
}

function Set-PlaneEnvFile {
    if (-not (Test-Path -LiteralPath $planeEnvExample)) {
        throw "Missing Plane env example at $planeEnvExample"
    }

    if ((Test-Path -LiteralPath $planeEnvFile) -and (-not $Force)) {
        Write-Host "Keeping existing Plane env: stacks/plane/plane.env. Use -Force to recreate it."
        return
    }

    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.AddRange([string[]](Get-Content -LiteralPath $planeEnvExample))

    $secretKey = Get-SecretText -Path $planeSecretKeyFile
    $postgresPassword = Get-SecretText -Path $planePostgresPasswordFile
    $rabbitmqPassword = Get-SecretText -Path $planeRabbitmqPasswordFile
    $minioPassword = Get-SecretText -Path $planeMinioPasswordFile
    $postgresPasswordEncoded = [uri]::EscapeDataString($postgresPassword)
    $rabbitmqPasswordEncoded = [uri]::EscapeDataString($rabbitmqPassword)

    Set-EnvValue -Lines $lines -Key "APP_DOMAIN" -Value "localhost"
    Set-EnvValue -Lines $lines -Key "APP_RELEASE" -Value "v1.3.1"
    Set-EnvValue -Lines $lines -Key "LISTEN_HTTP_PORT" -Value "8082"
    Set-EnvValue -Lines $lines -Key "LISTEN_HTTPS_PORT" -Value "8443"
    Set-EnvValue -Lines $lines -Key "WEB_URL" -Value "http://localhost:8082"
    Set-EnvValue -Lines $lines -Key "PLANE_DEBUG" -Value "0"
    Set-EnvValue -Lines $lines -Key "CORS_ALLOWED_ORIGINS" -Value "http://localhost:8082"
    Set-EnvValue -Lines $lines -Key "POSTGRES_PASSWORD" -Value $postgresPassword
    Set-EnvValue -Lines $lines -Key "DATABASE_URL" -Value "postgresql://plane:$postgresPasswordEncoded@plane-db/plane"
    Set-EnvValue -Lines $lines -Key "RABBITMQ_PASSWORD" -Value $rabbitmqPassword
    Set-EnvValue -Lines $lines -Key "AMQP_URL" -Value "amqp://plane:$rabbitmqPasswordEncoded@plane-mq:5672/plane"
    Set-EnvValue -Lines $lines -Key "SECRET_KEY" -Value $secretKey
    Set-EnvValue -Lines $lines -Key "LIVE_SERVER_SECRET_KEY" -Value $secretKey
    Set-EnvValue -Lines $lines -Key "AWS_SECRET_ACCESS_KEY" -Value $minioPassword

    Set-Content -LiteralPath $planeEnvFile -Value $lines -Encoding ascii
    Write-Host "Wrote local Plane env: stacks/plane/plane.env"
}
```

- [ ] **Step 3: Call the Plane env generator after secrets exist**

Add this line after the four Plane `Set-SecretFile` calls:

```powershell
Set-PlaneEnvFile
```

- [ ] **Step 4: Update the script's final startup message**

Replace:

```powershell
Write-Host "Start SigNoz with:"
Write-Host "docker compose --env-file .env -f stacks/signoz/compose.yaml up -d"
```

with:

```powershell
Write-Host "Start Ops Board with:"
Write-Host "docker compose --env-file .env -f compose.yaml up -d"
```

- [ ] **Step 5: Parse-check the PowerShell script**

Run:

```powershell
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\scripts\init-local-config.ps1), [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) { $errors | Format-List; throw "PowerShell parse errors found" }
```

Expected: exits `0` and prints no parse errors.

- [ ] **Step 6: Run local config bootstrap without rotating existing secrets**

Run:

```powershell
.\scripts\init-local-config.ps1
```

Expected:

- Existing `.env` is kept unless missing.
- Existing secret files are kept unless missing.
- Existing `stacks/plane/plane.env` is kept unless missing.
- The final startup message references `docker compose --env-file .env -f compose.yaml up -d`.

- [ ] **Step 7: Verify ignored local Plane env still validates**

Run:

```powershell
git check-ignore -v stacks/plane/plane.env
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml config --quiet
```

Expected:

- `git check-ignore` reports `stacks/plane/.gitignore`.
- Compose exits `0`.

- [ ] **Step 8: Commit root-ready local config**

```powershell
git add scripts/init-local-config.ps1
git commit -m "chore: generate plane env during local init"
```

---

### Task 4: Make Helper Scripts Understand `ops-board`

**Files:**
- Modify: `scripts/status.ps1`
- Modify: `scripts/update-stack.ps1`

- [ ] **Step 1: Update `scripts/status.ps1` default and compose-file resolution**

Replace the top of `scripts/status.ps1` through the `$stackEnvFiles` assignment with:

```powershell
param(
    [string]$Stack = "ops-board"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFile = Join-Path $repoRoot ".env"

if ($Stack -eq "ops-board") {
    $composeFile = Join-Path $repoRoot "compose.yaml"
    $stackEnvFiles = @()
}
else {
    $composeFile = Join-Path $repoRoot "stacks\$Stack\compose.yaml"
    $stackDir = Split-Path -Parent $composeFile
    $stackEnvFiles = @(
        (Join-Path $stackDir ".env"),
        (Join-Path $stackDir "$Stack.env")
    )
}
```

Keep the existing compose-file existence check and Docker command logic below that block.

- [ ] **Step 2: Update `scripts/update-stack.ps1` default and compose-file resolution**

Replace the top of `scripts/update-stack.ps1` through the `$stackEnvFiles` assignment with:

```powershell
param(
    [string]$Stack = "ops-board",
    [switch]$RemoveOrphans
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFile = Join-Path $repoRoot ".env"

if ($Stack -eq "ops-board") {
    $composeFile = Join-Path $repoRoot "compose.yaml"
    $stackEnvFiles = @()
}
else {
    $composeFile = Join-Path $repoRoot "stacks\$Stack\compose.yaml"
    $stackDir = Split-Path -Parent $composeFile
    $stackEnvFiles = @(
        (Join-Path $stackDir ".env"),
        (Join-Path $stackDir "$Stack.env")
    )
}
```

Keep the existing compose-file existence check, pull, up, and status logic below that block.

- [ ] **Step 3: Parse-check both helper scripts**

Run:

```powershell
$files = @(".\scripts\status.ps1", ".\scripts\update-stack.ps1")
foreach ($file in $files) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $file), [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count -gt 0) { $errors | Format-List; throw "PowerShell parse errors found in $file" }
}
```

Expected: exits `0` and prints no parse errors.

- [ ] **Step 4: Verify script commands resolve the root and per-stack compose files**

Run:

```powershell
.\scripts\status.ps1 -Stack ops-board
.\scripts\status.ps1 -Stack signoz
.\scripts\status.ps1 -Stack uptime-kuma
.\scripts\status.ps1 -Stack homepage
.\scripts\status.ps1 -Stack plane
```

Expected:

- `-Stack ops-board` uses root `compose.yaml`.
- Per-stack commands still resolve `stacks/<stack>/compose.yaml`.
- If the runtime migration has not happened yet, per-stack status shows the currently running individual project containers.

- [ ] **Step 5: Commit helper script support**

```powershell
git add scripts/status.ps1 scripts/update-stack.ps1
git commit -m "chore: support ops-board compose scripts"
```

---

### Task 5: Document The Aggregated Workflow And Clean Rebuild

**Files:**
- Modify: `README.md`
- Modify: `scripts/README.md`

- [ ] **Step 1: Update the root README layout**

Add `compose.yaml` to the root layout:

```text
ops-board/
  README.md
  compose.yaml
  .env.example
  .gitignore
```

- [ ] **Step 2: Replace the root README quick-start startup commands**

Replace the current rollout-order startup block:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml up -d
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml up -d
docker compose --env-file .env -f stacks/homepage/compose.yaml up -d
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml up -d
```

with:

```powershell
docker compose --env-file .env -f compose.yaml up -d
```

- [ ] **Step 3: Add an aggregator explanation to the root README**

Add this paragraph after the stack table:

```markdown
The root `compose.yaml` is the normal full-board entrypoint. It uses Docker Compose `include` to pull in the per-stack Compose files, so `stacks/signoz/compose.yaml`, `stacks/uptime-kuma/compose.yaml`, `stacks/homepage/compose.yaml`, and `stacks/plane/compose.yaml` remain the source of truth for their services.
```

- [ ] **Step 4: Add a clean rebuild section to the root README**

Add this section before `## Access Model`:

````markdown
## Clean Rebuild From Separate Projects

During this development phase, it is safe to wipe local stack data and rebuild under the root `ops-board` project:

```powershell
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml down -v
docker compose --env-file .env -f stacks/homepage/compose.yaml down -v
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml down -v
docker compose --env-file .env -f stacks/signoz/compose.yaml down -v
docker compose --env-file .env -f compose.yaml up -d
```

This deletes local Docker volumes for these stacks. Remove `-v` from each `down` command when preserving data becomes important.
````

- [ ] **Step 5: Update root README stack commands**

Replace the all-stack status block:

```powershell
.\scripts\status.ps1 -Stack signoz
.\scripts\status.ps1 -Stack uptime-kuma
.\scripts\status.ps1 -Stack homepage
.\scripts\status.ps1 -Stack plane
```

with:

```powershell
.\scripts\status.ps1
```

Add this after the default status command:

```markdown
Use individual stack names only when intentionally operating a stack outside the root aggregator:

```powershell
.\scripts\status.ps1 -Stack signoz
.\scripts\status.ps1 -Stack uptime-kuma
.\scripts\status.ps1 -Stack homepage
.\scripts\status.ps1 -Stack plane
```
```

- [ ] **Step 6: Update `scripts/README.md` defaults**

Change the opening description to state:

```markdown
All stack-aware scripts look for root `compose.yaml` when `-Stack ops-board` is used. `ops-board` is the default. Individual stack names still resolve to `stacks/<stack>/compose.yaml` for isolated maintenance.
```

Change the default status example section to:

```markdown
Shows Docker Compose status for one stack. It includes completed one-shot services such as init and migration jobs, and defaults to the root Ops Board aggregator:

```powershell
.\scripts\status.ps1
```
```

Change the default update example section to:

```markdown
Pulls images for a stack and runs `docker compose up -d`. It defaults to the root Ops Board aggregator:

```powershell
.\scripts\update-stack.ps1
```
```

- [ ] **Step 7: Verify Markdown and Compose docs**

Run:

```powershell
docker compose --env-file .env -f compose.yaml config --quiet
git diff --check
```

Expected:

- Compose exits `0`.
- `git diff --check` exits `0`.

- [ ] **Step 8: Commit docs**

```powershell
git add README.md scripts/README.md
git commit -m "docs: document ops-board compose aggregator"
```

---

### Task 6: Clean Rebuild Runtime Under The Root Project And Verify

**Files:**
- No file changes expected.

- [ ] **Step 1: Confirm current runtime state**

Run:

```powershell
.\scripts\status.ps1 -Stack signoz
.\scripts\status.ps1 -Stack uptime-kuma
.\scripts\status.ps1 -Stack homepage
.\scripts\status.ps1 -Stack plane
```

Expected: current individual projects are visible if they are still running.

- [ ] **Step 2: Stop individual projects and delete development volumes**

Run:

```powershell
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml down -v
docker compose --env-file .env -f stacks/homepage/compose.yaml down -v
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml down -v
docker compose --env-file .env -f stacks/signoz/compose.yaml down -v
```

Expected:

- Containers stop and are removed.
- Local named volumes for the current development stack data are deleted.

- [ ] **Step 3: Verify old development volumes were removed**

Run:

```powershell
docker volume ls --format "{{.Name}}" | Select-String -Pattern "^(signoz-clickhouse|signoz-sqlite|signoz-zookeeper-1|uptime-kuma-data|plane_pgdata|plane_redisdata|plane_uploads|plane_rabbitmq_data|plane_proxy_config|plane_proxy_data)$"
```

Expected: no output for the old development volumes before the root project is started.

- [ ] **Step 4: Start the root Ops Board project**

Run:

```powershell
docker compose --env-file .env -f compose.yaml up -d
```

Expected:

- The Compose project is `ops-board`.
- Fixed-name services such as `signoz`, `homepage`, and `uptime-kuma` start.
- Plane services start under the root project and publish `0.0.0.0:8082->80/tcp`.
- Fresh named volumes are created for the root rebuild.

- [ ] **Step 5: Verify root status**

Run:

```powershell
.\scripts\status.ps1
```

Expected: output includes SigNoz, Uptime Kuma, Homepage, and Plane services.

- [ ] **Step 6: Verify HTTP endpoints**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8080/api/v1/health -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:13133/ -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:3001 -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:3000 -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing http://localhost:8082 -TimeoutSec 60
```

Expected:

- SigNoz health returns `200`.
- Collector health returns `200`.
- Uptime Kuma returns `200`.
- Homepage returns `200`.
- Plane returns `200` or another successful first-run response.

- [ ] **Step 7: Verify Git hygiene**

Run:

```powershell
git diff --check
git status --short --branch
```

Expected:

- `git diff --check` exits `0`.
- `git status --short --branch` shows no uncommitted changes.

---

## Rollback

If the root aggregator start fails after the clean rebuild, go back to the per-stack projects with fresh volumes:

```powershell
docker compose --env-file .env -f compose.yaml down -v
docker compose --env-file .env -f stacks/signoz/compose.yaml up -d
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml up -d
docker compose --env-file .env -f stacks/homepage/compose.yaml up -d
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml up -d
```

This rollback also starts with fresh data because the existing environment is still development-only.

---

## Self-Review

- Spec coverage: The plan keeps per-stack Compose files as source of truth, adds a root `compose.yaml` aggregator using `include`, updates scripts and docs, and provides a safe migration path to one `ops-board` project.
- Placeholder scan: No unresolved implementation placeholders are present. The plan includes exact YAML, PowerShell snippets, commands, and expected results.
- Data policy: The user approved clearing existing local data because the stack is still development-only. Plane volume names are still pinned so future root and per-stack runs use predictable stack-specific volume names.
- Compatibility: The existing Docker Compose version is new enough for `include`, and the earlier config probe validated the include approach when the project directory is the repo root.

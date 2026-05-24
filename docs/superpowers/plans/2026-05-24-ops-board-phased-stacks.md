# Ops Board Phased Stacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Uptime Kuma, Homepage, and Plane to Ops Board in a phased rollout where each stack is independently runnable and verified before the next stack is added.

**Architecture:** Keep one Docker Compose project per stack under `stacks/<stack>/`, with top-level Compose `name:` set inside each compose file. Use the repo root `.env` for non-secret knobs, ignored `secrets/` files for sensitive values, Tailscale/MagicDNS for private access, and no reverse proxy. Uptime Kuma becomes the health source, Homepage becomes the private launch board, and Plane is added last after the lighter ops layer is stable.

**Tech Stack:** Docker Compose v2, PowerShell helper scripts, Uptime Kuma, Homepage, Plane Community Edition, Tailscale, Markdown.

---

## Source Notes

- Docker Compose supports top-level `name:` as the default project name when `-p` is not supplied: https://docs.docker.com/reference/compose-file/version-and-name/
- Docker Compose secrets are explicitly granted to services and can be sourced from files: https://docs.docker.com/reference/compose-file/secrets/
- Uptime Kuma Docker docs use image `louislam/uptime-kuma:2`, port `3001`, and `/app/data`; their docs warn to keep SQLite data on storage with POSIX file locks: https://github.com/louislam/uptime-kuma/wiki/%F0%9F%94%A7-How-to-Install
- Homepage Docker docs use `ghcr.io/gethomepage/homepage`, config mounted at `/app/config`, and require `HOMEPAGE_ALLOWED_HOSTS`: https://gethomepage.dev/installation/docker/
- Homepage has an Uptime Kuma widget that reads from a Kuma status page slug: https://gethomepage.dev/widgets/services/uptime-kuma/
- Plane Community Edition is AGPL v3 and suitable for evaluating/auditing how services work together: https://developers.plane.so/self-hosting/editions-and-versions
- Plane Community Docker Compose install uses the official `setup.sh` flow and requires Docker, Docker Compose, and Bash/Git Bash on Windows: https://developers.plane.so/self-hosting/methods/docker-compose

---

## File Structure

Create or modify these paths:

- Modify: `.env.example` - add shared public URLs, stack ports, and image tags for Uptime Kuma, Homepage, and Plane.
- Modify: `.gitignore` - ignore stack-local env files and Plane generated runtime/config artifacts that should not be committed.
- Modify: `scripts/init-local-config.ps1` - create stack secret files and keep existing local `.env` behavior.
- Modify: `scripts/README.md` - document new stack commands and per-stack usage.
- Modify: `README.md` - update stack statuses, layout, and quick-start order.
- Create: `stacks/uptime-kuma/compose.yaml` - Uptime Kuma Compose project.
- Create: `stacks/uptime-kuma/README.md` - setup, first-run, status page, monitor checklist, and reset notes.
- Create: `stacks/uptime-kuma/docs/monitors.md` - manual monitor definitions for SigNoz, Homepage, and Plane.
- Create: `stacks/homepage/compose.yaml` - Homepage Compose project.
- Create: `stacks/homepage/config/settings.yaml` - Homepage visual/runtime settings.
- Create: `stacks/homepage/config/services.yaml` - links and widgets for Ops Board services.
- Create: `stacks/homepage/config/widgets.yaml` - small local info widgets.
- Create: `stacks/homepage/config/bookmarks.yaml` - docs and ops references.
- Create: `stacks/homepage/README.md` - setup, access, config, and Uptime Kuma widget notes.
- Create: `stacks/plane/.gitignore` - ignore Plane local env/runtime files.
- Create: `stacks/plane/README.md` - Plane edition decision, install flow, ports, and verification.
- Create: `stacks/plane/plane.env.example` - sanitized local Plane env baseline after acquiring official files.
- Create or vendor: `stacks/plane/compose.yaml` - official Plane Community Compose file acquired from Plane's setup flow and adjusted only for repo placement and port conflicts.

Out of scope for this plan:

- Public reverse proxy, public TLS, or public DNS.
- Homepage Docker socket integration.
- Automated Uptime Kuma monitor creation through unsupported/internal APIs.
- Production-grade Plane external database/object storage.
- Healthchecks.io-compatible service; keep it optional until Uptime Kuma is working.

---

## Implementation Tasks

### Task 1: Shared Stack Defaults And Ignore Rules

**Files:**
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `scripts/README.md`
- Modify: `README.md`

- [ ] **Step 1: Add shared URLs, image tags, and ports to `.env.example`**

Add this block after the existing SigNoz/HISTOGRAM settings:

```dotenv
# Public URLs used by Homepage links and docs.
# Use localhost for first local setup. Change these to Tailscale MagicDNS URLs
# when accessing from other tailnet devices.
SIGNOZ_PUBLIC_URL=http://localhost:8080

# Uptime Kuma
UPTIME_KUMA_VERSION=2
UPTIME_KUMA_PORT=3001
UPTIME_KUMA_PUBLIC_URL=http://localhost:3001
UPTIME_KUMA_STATUS_SLUG=ops-board

# Homepage
HOMEPAGE_VERSION=v1.13.1
HOMEPAGE_PORT=3000
HOMEPAGE_PUBLIC_URL=http://localhost:3000
HOMEPAGE_ALLOWED_HOSTS=localhost:3000,127.0.0.1:3000,your-hostname:3000

# Plane
PLANE_HTTP_PORT=8082
PLANE_PUBLIC_URL=http://localhost:8082
PLANE_WEB_URL=http://localhost:8082
```

- [ ] **Step 2: Update `.gitignore` for stack-local env and generated Plane files**

Add this block below the existing local environment entries:

```gitignore
# Stack-local environment files
/stacks/*/*.env
!/stacks/*/*.env.example
```

Add this block below the runtime data section:

```gitignore
# Plane generated installer/runtime files
/stacks/plane/plane-selfhost/
/stacks/plane/plane-app/
/stacks/plane/plane-app-preview/
```

- [ ] **Step 3: Update root README stack status language**

Change the stack table statuses to:

```markdown
| Stack | Purpose | Status |
|-------|---------|--------|
| SigNoz | Central observability for logs, traces, metrics, and telemetry ingestion | Active |
| Uptime Kuma | Uptime and endpoint monitoring | Planned in this rollout |
| Homepage | Private dashboard and service directory | Planned after Uptime Kuma |
| Plane | Project and kanban management | Planned after Homepage |
| Healthchecks | Scheduled job monitoring | Optional later |
```

Replace the current single-runnable-stack sentence with:

```markdown
SigNoz is already runnable. This rollout adds Uptime Kuma first, Homepage second, and Plane last.
```

- [ ] **Step 4: Add stack command examples to `scripts/README.md`**

Add this section after the `status.ps1` section:

````markdown
Common stack names:

```powershell
.\scripts\status.ps1 -Stack signoz
.\scripts\status.ps1 -Stack uptime-kuma
.\scripts\status.ps1 -Stack homepage
.\scripts\status.ps1 -Stack plane
```
````

Add this section after the `update-stack.ps1` section:

````markdown
Update a specific stack:

```powershell
.\scripts\update-stack.ps1 -Stack uptime-kuma
.\scripts\update-stack.ps1 -Stack homepage
.\scripts\update-stack.ps1 -Stack plane
```
````

- [ ] **Step 5: Verify docs and Compose baseline**

Run:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml config --quiet
git diff --check
```

Expected:

- Compose exits `0`.
- `git diff --check` exits `0`.

- [ ] **Step 6: Commit shared defaults**

```powershell
git add .env.example .gitignore README.md scripts/README.md
git commit -m "chore: add shared stack defaults"
```

---

### Task 2: Uptime Kuma Stack

**Files:**
- Create: `stacks/uptime-kuma/compose.yaml`
- Create: `stacks/uptime-kuma/README.md`
- Create: `stacks/uptime-kuma/docs/monitors.md`
- Modify: `README.md`

- [ ] **Step 1: Create `stacks/uptime-kuma/compose.yaml`**

```yaml
name: uptime-kuma

services:
  uptime-kuma:
    image: louislam/uptime-kuma:${UPTIME_KUMA_VERSION:-2}
    container_name: uptime-kuma
    restart: unless-stopped
    ports:
      - "0.0.0.0:${UPTIME_KUMA_PORT:-3001}:3001"
    volumes:
      - uptime-kuma-data:/app/data
    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  uptime-kuma-data:
    name: uptime-kuma-data
```

- [ ] **Step 2: Create `stacks/uptime-kuma/README.md`**

````markdown
# Uptime Kuma Stack

Private uptime and endpoint monitoring for Ops Board.

## Quick Start

From the repo root:

```powershell
.\scripts\init-local-config.ps1
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml up -d
```

Open:

```text
http://localhost:3001
```

From another tailnet device, use:

```text
http://<tailscale-hostname>:3001
```

## First Run

Create the first Uptime Kuma admin account in the web UI.

Create a status page with this slug:

```text
ops-board
```

Homepage uses that status page slug for its Uptime Kuma widget.

## Storage

Uptime Kuma stores SQLite data under `/app/data` in the Docker volume `uptime-kuma-data`.

Keep this data on local Docker-managed storage. Do not move it to NFS, cloud sync folders, or remote filesystems because SQLite needs reliable file locking.

## Monitor Targets

See `docs/monitors.md`.

## Commands

Show status:

```powershell
.\scripts\status.ps1 -Stack uptime-kuma
```

Stop while preserving data:

```powershell
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml down
```

Reset and delete the Uptime Kuma volume:

```powershell
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml down -v
```
````

- [ ] **Step 3: Create `stacks/uptime-kuma/docs/monitors.md`**

````markdown
# Uptime Kuma Monitors

Create these monitors manually in Uptime Kuma after first-account setup.

Use `host.docker.internal` for same-host checks from the Uptime Kuma container. The compose file maps `host.docker.internal` through Docker's host gateway.

## Initial Monitors

| Name | Type | URL | Expected |
|------|------|-----|----------|
| SigNoz UI | HTTP(s) | `http://host.docker.internal:8080/api/v1/health` | `200` |
| SigNoz Collector | HTTP(s) | `http://host.docker.internal:13133/` | `200` |

## Add After Homepage

| Name | Type | URL | Expected |
|------|------|-----|----------|
| Homepage | HTTP(s) | `http://host.docker.internal:3000` | `200` |

## Add After Plane

| Name | Type | URL | Expected |
|------|------|-----|----------|
| Plane | HTTP(s) | `http://host.docker.internal:8082` | `200`, `302`, or app-specific healthy response |

## Status Page

Create one status page:

```text
Slug: ops-board
Title: Ops Board
```

Add the monitors above to the status page as each stack becomes available.
````

- [ ] **Step 4: Update root README layout and status**

Add this to the layout under `stacks/`:

```text
    uptime-kuma/
      compose.yaml
      docs/
      README.md
```

Change Uptime Kuma table status to `Active`.

- [ ] **Step 5: Validate Uptime Kuma Compose config**

Run:

```powershell
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml config --quiet
```

Expected: exits `0`.

- [ ] **Step 6: Start Uptime Kuma**

Run:

```powershell
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml up -d
```

Expected: container `uptime-kuma` starts and publishes `0.0.0.0:3001->3001/tcp`.

- [ ] **Step 7: Verify Uptime Kuma HTTP access**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:3001 -TimeoutSec 20
.\scripts\status.ps1 -Stack uptime-kuma
```

Expected:

- HTTP request returns a successful response.
- Status output includes `uptime-kuma`.

- [ ] **Step 8: Commit Uptime Kuma**

```powershell
git add README.md stacks/uptime-kuma
git commit -m "feat: add uptime kuma stack"
```

---

### Task 3: Homepage Stack

**Files:**
- Create: `stacks/homepage/compose.yaml`
- Create: `stacks/homepage/config/settings.yaml`
- Create: `stacks/homepage/config/services.yaml`
- Create: `stacks/homepage/config/widgets.yaml`
- Create: `stacks/homepage/config/bookmarks.yaml`
- Create: `stacks/homepage/README.md`
- Modify: `README.md`

- [ ] **Step 1: Create `stacks/homepage/compose.yaml`**

```yaml
name: homepage

services:
  homepage:
    image: ghcr.io/gethomepage/homepage:${HOMEPAGE_VERSION:-v1.13.1}
    container_name: homepage
    restart: unless-stopped
    ports:
      - "0.0.0.0:${HOMEPAGE_PORT:-3000}:3000"
    volumes:
      - ./config:/app/config
    environment:
      HOMEPAGE_ALLOWED_HOSTS: ${HOMEPAGE_ALLOWED_HOSTS:-localhost:3000,127.0.0.1:3000}
      HOMEPAGE_VAR_SIGNOZ_URL: ${SIGNOZ_PUBLIC_URL:-http://localhost:8080}
      HOMEPAGE_VAR_UPTIME_KUMA_URL: ${UPTIME_KUMA_PUBLIC_URL:-http://localhost:3001}
      HOMEPAGE_VAR_HOMEPAGE_URL: ${HOMEPAGE_PUBLIC_URL:-http://localhost:3000}
      HOMEPAGE_VAR_PLANE_URL: ${PLANE_PUBLIC_URL:-http://localhost:8082}
      HOMEPAGE_VAR_UPTIME_KUMA_STATUS_SLUG: ${UPTIME_KUMA_STATUS_SLUG:-ops-board}
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

- [ ] **Step 2: Create `stacks/homepage/config/settings.yaml`**

```yaml
title: Ops Board
theme: dark
color: slate
headerStyle: clean
target: _blank
hideVersion: true
layout:
  Observability:
    style: row
    columns: 3
  Project Management:
    style: row
    columns: 3
  References:
    style: row
    columns: 3
```

- [ ] **Step 3: Create `stacks/homepage/config/services.yaml`**

```yaml
- Observability:
    - SigNoz:
        href: "{{HOMEPAGE_VAR_SIGNOZ_URL}}"
        description: Logs, traces, metrics, and OTLP ingestion
        ping: "{{HOMEPAGE_VAR_SIGNOZ_URL}}/api/v1/health"
    - Uptime Kuma:
        href: "{{HOMEPAGE_VAR_UPTIME_KUMA_URL}}"
        description: Endpoint and uptime monitoring
        widget:
          type: uptimekuma
          url: "{{HOMEPAGE_VAR_UPTIME_KUMA_URL}}"
          slug: "{{HOMEPAGE_VAR_UPTIME_KUMA_STATUS_SLUG}}"
    - Homepage:
        href: "{{HOMEPAGE_VAR_HOMEPAGE_URL}}"
        description: Private service directory

- Project Management:
    - Plane:
        href: "{{HOMEPAGE_VAR_PLANE_URL}}"
        description: Project and kanban management
```

- [ ] **Step 4: Create `stacks/homepage/config/widgets.yaml`**

```yaml
- datetime:
    text_size: xl
    format:
      dateStyle: medium
      timeStyle: short

- search:
    provider: duckduckgo
    target: _blank
```

- [ ] **Step 5: Create `stacks/homepage/config/bookmarks.yaml`**

```yaml
- References:
    - Ops Board GitHub:
        - href: https://github.com/Wenjun-Mao/ops-board
          description: Repository
    - SigNoz Docs:
        - href: https://signoz.io/docs/
          description: Observability docs
    - Uptime Kuma:
        - href: https://github.com/louislam/uptime-kuma
          description: Monitoring project
    - Homepage Docs:
        - href: https://gethomepage.dev/
          description: Dashboard docs
    - Plane Docs:
        - href: https://developers.plane.so/self-hosting/overview
          description: Self-hosting docs
```

- [ ] **Step 6: Create `stacks/homepage/README.md`**

````markdown
# Homepage Stack

Private service directory for Ops Board.

## Quick Start

From the repo root:

```powershell
.\scripts\init-local-config.ps1
docker compose --env-file .env -f stacks/homepage/compose.yaml up -d
```

Open:

```text
http://localhost:3000
```

From another tailnet device:

```text
http://<tailscale-hostname>:3000
```

## Configuration

Homepage config lives in `config/`.

The compose file does not mount the Docker socket. Service links and widgets are explicit so the dashboard works the same way across local machines and VPS hosts.

## Uptime Kuma Widget

The Uptime Kuma widget reads from the status page slug in `.env`:

```dotenv
UPTIME_KUMA_STATUS_SLUG=ops-board
```

Create that status page in Uptime Kuma before expecting the widget to show useful data.

## Commands

Show status:

```powershell
.\scripts\status.ps1 -Stack homepage
```

Stop:

```powershell
docker compose --env-file .env -f stacks/homepage/compose.yaml down
```
````

- [ ] **Step 7: Update root README layout and status**

Add this to the layout under `stacks/`:

```text
    homepage/
      compose.yaml
      config/
        bookmarks.yaml
        services.yaml
        settings.yaml
        widgets.yaml
      README.md
```

Change Homepage table status to `Active`.

- [ ] **Step 8: Validate Homepage Compose config**

Run:

```powershell
docker compose --env-file .env -f stacks/homepage/compose.yaml config --quiet
```

Expected: exits `0`.

- [ ] **Step 9: Start Homepage**

Run:

```powershell
docker compose --env-file .env -f stacks/homepage/compose.yaml up -d
```

Expected: container `homepage` starts and publishes `0.0.0.0:3000->3000/tcp`.

- [ ] **Step 10: Verify Homepage HTTP access**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:3000 -TimeoutSec 20
.\scripts\status.ps1 -Stack homepage
```

Expected:

- HTTP request returns a successful response.
- Status output includes `homepage`.

- [ ] **Step 11: Add Homepage monitor to Uptime Kuma**

In Uptime Kuma UI, create:

```text
Name: Homepage
Type: HTTP(s)
URL: http://host.docker.internal:3000
Expected status: 200
Status page: ops-board
```

- [ ] **Step 12: Commit Homepage**

```powershell
git add README.md stacks/homepage
git commit -m "feat: add homepage stack"
```

---

### Task 4: Plane Preparation And Secrets

**Files:**
- Modify: `.gitignore`
- Modify: `scripts/init-local-config.ps1`
- Create: `stacks/plane/.gitignore`
- Create: `stacks/plane/README.md`
- Create: `stacks/plane/plane.env.example`

- [ ] **Step 1: Add Plane stack ignore file**

Create `stacks/plane/.gitignore`:

```gitignore
plane.env
plane-selfhost/
plane-app/
plane-app-preview/
```

- [ ] **Step 2: Extend `scripts/init-local-config.ps1` with Plane secrets**

Add these variables after `$signozJwtSecretFile`:

```powershell
$planeSecretKeyFile = Join-Path $secretsDir "plane_secret_key"
$planePostgresPasswordFile = Join-Path $secretsDir "plane_postgres_password"
$planeRabbitmqPasswordFile = Join-Path $secretsDir "plane_rabbitmq_password"
$planeMinioPasswordFile = Join-Path $secretsDir "plane_minio_password"
```

Add this helper after `New-SecretValue`:

```powershell
function Set-SecretFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if ((-not (Test-Path -LiteralPath $Path)) -or $Force) {
        New-SecretValue | Set-Content -LiteralPath $Path -NoNewline -Encoding ascii
        Write-Host "Wrote Docker secret: $Label"
    }
    else {
        Write-Host "Keeping existing Docker secret: $Label. Use -Force to rotate it."
    }
}
```

Replace the existing SigNoz secret block:

```powershell
if ((-not (Test-Path -LiteralPath $signozJwtSecretFile)) -or $Force) {
    New-SecretValue | Set-Content -LiteralPath $signozJwtSecretFile -NoNewline -Encoding ascii
    Write-Host "Wrote Docker secret: secrets/signoz_jwt_secret"
}
else {
    Write-Host "Keeping existing Docker secret: secrets/signoz_jwt_secret. Use -Force to rotate it."
}
```

with:

```powershell
Set-SecretFile -Path $signozJwtSecretFile -Label "secrets/signoz_jwt_secret"
Set-SecretFile -Path $planeSecretKeyFile -Label "secrets/plane_secret_key"
Set-SecretFile -Path $planePostgresPasswordFile -Label "secrets/plane_postgres_password"
Set-SecretFile -Path $planeRabbitmqPasswordFile -Label "secrets/plane_rabbitmq_password"
Set-SecretFile -Path $planeMinioPasswordFile -Label "secrets/plane_minio_password"
```

- [ ] **Step 3: Create `stacks/plane/plane.env.example` baseline**

```dotenv
# Plane Community Edition local defaults.
# The final plane.env must be reconciled with the official Plane setup output.

LISTEN_HTTP_PORT=8082
LISTEN_HTTPS_PORT=8443
WEB_URL=http://localhost:8082
CORS_ALLOWED_ORIGINS=http://localhost:8082

POSTGRES_USER=plane
POSTGRES_DB=plane
POSTGRES_PASSWORD_FILE=../../secrets/plane_postgres_password

RABBITMQ_USER=plane
RABBITMQ_VHOST=plane
RABBITMQ_PASSWORD_FILE=../../secrets/plane_rabbitmq_password

SECRET_KEY_FILE=../../secrets/plane_secret_key
AWS_ACCESS_KEY_ID=plane
AWS_SECRET_ACCESS_KEY_FILE=../../secrets/plane_minio_password
AWS_S3_BUCKET_NAME=plane-uploads
```

- [ ] **Step 4: Create `stacks/plane/README.md`**

````markdown
# Plane Stack

Project and kanban management for Ops Board.

## Edition

This repo starts with Plane Community Edition.

Community Edition is AGPL v3 and is the best fit for this repo's first Plane pass because it is auditable and self-contained. Commercial Edition can be evaluated after the Community stack is working.

## Install Model

Do not hand-write Plane's compose file from memory.

Use Plane's official setup flow to acquire the current Community Edition `docker-compose.yaml` and `plane.env`, then adapt the generated files into this folder with the smallest possible changes:

- rename `docker-compose.yaml` to `compose.yaml`
- add top-level `name: plane`
- avoid port `8080` because SigNoz already uses it
- keep `plane.env` ignored
- keep `plane.env.example` sanitized and committed

## Access

Local:

```text
http://localhost:8082
```

Tailnet:

```text
http://<tailscale-hostname>:8082
```

## Commands

Show status:

```powershell
.\scripts\status.ps1 -Stack plane
```

Start after `compose.yaml` and `plane.env` exist:

```powershell
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml up -d
```

Stop:

```powershell
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml down
```
````

- [ ] **Step 5: Run init-local-config and verify generated secret files are ignored**

Run:

```powershell
.\scripts\init-local-config.ps1
git check-ignore -v secrets/plane_secret_key secrets/plane_postgres_password secrets/plane_rabbitmq_password secrets/plane_minio_password
```

Expected:

- Each `secrets/plane_*` path is ignored by `.gitignore`.

- [ ] **Step 6: Commit Plane preparation**

```powershell
git add .gitignore scripts/init-local-config.ps1 stacks/plane/.gitignore stacks/plane/README.md stacks/plane/plane.env.example
git commit -m "chore: prepare plane stack secrets"
```

---

### Task 5: Acquire And Integrate Plane Community Compose

**Files:**
- Create or vendor: `stacks/plane/compose.yaml`
- Create local ignored file: `stacks/plane/plane.env`
- Modify: `stacks/plane/plane.env.example`
- Modify: `README.md`
- Modify: `stacks/homepage/config/services.yaml`
- Modify: `stacks/uptime-kuma/docs/monitors.md`

- [ ] **Step 1: Use Git Bash to acquire official Plane Community files**

Run from repo root in Git Bash:

```bash
mkdir -p stacks/plane/plane-selfhost
cd stacks/plane/plane-selfhost
curl -fsSL -o setup.sh https://github.com/makeplane/plane/releases/latest/download/setup.sh
chmod +x setup.sh
./setup.sh
```

At the prompt, choose:

```text
1) Install
8) Exit
```

Expected:

- A generated Plane app folder exists under `stacks/plane/plane-selfhost/`.
- That generated folder contains a Docker Compose file and env file.

- [ ] **Step 2: Copy official generated files into the stack folder**

Use PowerShell to identify generated files:

```powershell
Get-ChildItem -Recurse stacks/plane/plane-selfhost -Filter docker-compose.yaml
Get-ChildItem -Recurse stacks/plane/plane-selfhost -Filter plane.env
```

Copy the generated compose file to:

```text
stacks/plane/compose.yaml
```

Copy the generated env file to:

```text
stacks/plane/plane.env
```

Do not commit `stacks/plane/plane.env`.

- [ ] **Step 3: Adapt `stacks/plane/compose.yaml`**

Make these targeted changes only:

```yaml
name: plane
```

Ensure the compose file loads the stack-local env file when it references `env_file`:

```yaml
env_file:
  - plane.env
```

Ensure the main published HTTP port uses the local no-conflict value:

```yaml
ports:
  - "${LISTEN_HTTP_PORT:-8082}:80"
```

If the generated compose file already uses `${LISTEN_HTTP_PORT}:80`, keep that mapping and set `LISTEN_HTTP_PORT=8082` in `stacks/plane/plane.env`.

- [ ] **Step 4: Adapt `stacks/plane/plane.env` local values**

Set these exact local values:

```dotenv
LISTEN_HTTP_PORT=8082
WEB_URL=http://localhost:8082
CORS_ALLOWED_ORIGINS=http://localhost:8082
```

If the generated env file uses `APP_BASE_URL` instead of `WEB_URL`, set:

```dotenv
APP_BASE_URL=http://localhost:8082
```

Keep generated database, Redis/Valkey, RabbitMQ, and object-storage variable names intact.

- [ ] **Step 5: Sanitize `plane.env.example` from the generated env**

Copy the final key list from `stacks/plane/plane.env` into `stacks/plane/plane.env.example`, replacing secrets with non-secret placeholders.

Use these values for the top access fields:

```dotenv
LISTEN_HTTP_PORT=8082
WEB_URL=http://localhost:8082
CORS_ALLOWED_ORIGINS=http://localhost:8082
```

Use this placeholder style for secret values:

```dotenv
POSTGRES_PASSWORD=change-me
RABBITMQ_PASSWORD=change-me
SECRET_KEY=change-me
AWS_SECRET_ACCESS_KEY=change-me
```

- [ ] **Step 6: Validate Plane Compose config**

Run:

```powershell
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml config --quiet
```

Expected: exits `0`.

- [ ] **Step 7: Start Plane**

Run:

```powershell
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml up -d
```

Expected:

- Plane services start.
- The app publishes `localhost:8082`.

- [ ] **Step 8: Verify Plane HTTP access**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8082 -TimeoutSec 60
.\scripts\status.ps1 -Stack plane
```

Expected:

- HTTP request returns `200`, `302`, or a Plane first-run/setup response.
- Status output includes Plane services.

- [ ] **Step 9: Update Homepage Plane link if needed**

If Plane is accessible at `http://localhost:8082`, keep:

```yaml
    - Plane:
        href: "{{HOMEPAGE_VAR_PLANE_URL}}"
        description: Project and kanban management
```

If the generated Plane stack uses a different local port, update `.env.example`, `.env`, `stacks/homepage/config/services.yaml`, and `stacks/plane/README.md` to the same port.

- [ ] **Step 10: Add Plane monitor to Uptime Kuma**

In Uptime Kuma UI, create:

```text
Name: Plane
Type: HTTP(s)
URL: http://host.docker.internal:8082
Expected status: 200, 302, or accepted first-run status
Status page: ops-board
```

- [ ] **Step 11: Update root README layout and status**

Add this to the layout under `stacks/`:

```text
    plane/
      compose.yaml
      plane.env.example
      README.md
```

Change Plane table status to `Active`.

- [ ] **Step 12: Commit Plane**

```powershell
git add README.md stacks/plane/compose.yaml stacks/plane/plane.env.example stacks/plane/README.md stacks/homepage/config/services.yaml stacks/uptime-kuma/docs/monitors.md
git commit -m "feat: add plane stack"
```

---

### Task 6: Final Integration Verification

**Files:**
- Modify: `README.md`
- Modify: `scripts/README.md`

- [ ] **Step 1: Add final root quick-start command block**

Add this to `README.md` after the current SigNoz quick start:

````markdown
Start the ops-board stacks in rollout order:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml up -d
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml up -d
docker compose --env-file .env -f stacks/homepage/compose.yaml up -d
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml up -d
```
````

- [ ] **Step 2: Add final status command block**

Add this to `README.md` under Stack Commands:

````markdown
Show all stack statuses:

```powershell
.\scripts\status.ps1 -Stack signoz
.\scripts\status.ps1 -Stack uptime-kuma
.\scripts\status.ps1 -Stack homepage
.\scripts\status.ps1 -Stack plane
```
````

- [ ] **Step 3: Validate every Compose config**

Run:

```powershell
docker compose --env-file .env -f stacks/signoz/compose.yaml config --quiet
docker compose --env-file .env -f stacks/uptime-kuma/compose.yaml config --quiet
docker compose --env-file .env -f stacks/homepage/compose.yaml config --quiet
docker compose --env-file stacks/plane/plane.env -f stacks/plane/compose.yaml config --quiet
```

Expected:

- All four commands exit `0`.

- [ ] **Step 4: Verify HTTP endpoints**

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
- Uptime Kuma returns a successful response.
- Homepage returns a successful response.
- Plane returns `200`, `302`, or a Plane first-run/setup response.

- [ ] **Step 5: Verify Git hygiene**

Run:

```powershell
git diff --check
git status --short --branch
git check-ignore -v .env secrets/signoz_jwt_secret secrets/plane_secret_key stacks/plane/plane.env
```

Expected:

- `git diff --check` exits `0`.
- `git status --short --branch` shows only intentional tracked changes before final commit.
- Ignored local secret/env paths are reported by `git check-ignore`.

- [ ] **Step 6: Commit final docs**

```powershell
git add README.md scripts/README.md
git commit -m "docs: document ops-board stack rollout"
```

---

## Rollout Checkpoints

Stop after each checkpoint and confirm the stack is reachable before continuing:

1. SigNoz remains healthy at `http://localhost:8080/api/v1/health`.
2. Uptime Kuma is reachable at `http://localhost:3001` and has first admin account plus `ops-board` status page.
3. Homepage is reachable at `http://localhost:3000` and links to SigNoz and Uptime Kuma.
4. Plane is reachable at `http://localhost:8082`.
5. Uptime Kuma monitors include SigNoz UI, SigNoz Collector, Homepage, and Plane.
6. Homepage includes SigNoz, Uptime Kuma, Homepage, and Plane service entries.

## Self-Review

- Spec coverage: The plan covers phased rollout, Uptime Kuma first, Homepage second, Plane last, per-stack Compose `name:`, `.env` for non-secret config, local secrets, Tailscale-first access, and no reverse proxy.
- Placeholder scan: No unresolved placeholders are present. Values like `change-me` are intentional committed examples for local secret replacement.
- Type and path consistency: Stack names are `signoz`, `uptime-kuma`, `homepage`, and `plane`; compose paths use `stacks/<stack>/compose.yaml`; Plane's local env path is consistently `stacks/plane/plane.env`.

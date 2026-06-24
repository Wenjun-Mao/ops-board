# Obvious Onboarding Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Ops Board onboarding docs almost embarrassingly obvious for a colleague onboarding a separate Python project.

**Architecture:** Use `docs/onboarding/human-guide.md` as the golden path and make `ops-board.yaml` the default first-success config channel. Keep `docs/onboarding/codex-guide.md` aligned with the same path, use `docs/onboarding/onboarding-contract.md` as the reference contract, and keep playground docs explicitly scoped as repo-local examples.

**Tech Stack:** Markdown docs, `ops-board-observe`, `uv`, YAML config through `ops-board.yaml`, `OPS_BOARD_*` environment variables for Docker/CI, existing pytest/Ruff/Compose verification.

---

## Root Cause Note

The docs issue is broader than one unclear sentence. The current guide names config fields but does not clearly say where a teammate should put them, how `bootstrap_observability()` reads them, or which config channel is the default first-success path. The durable fix belongs in the docs contract layer: make the human guide teach one obvious path first, then make the agent guide and reference contract agree with it.

## File Structure

Modify these docs:

```text
docs/onboarding/human-guide.md
docs/onboarding/codex-guide.md
docs/onboarding/onboarding-contract.md
examples/onboarding/README.md
examples/onboarding/dummy-api/README.md
examples/onboarding/dummy-job/README.md
```

No Python package behavior changes are planned. No ADR is required because this clarifies the existing package/config contract instead of changing it.

## Task 1: Rewrite Human Guide Around One First-Success Path

**Files:**
- Modify: `docs/onboarding/human-guide.md`

- [ ] **Step 1: Replace the vague package setup section**

In `docs/onboarding/human-guide.md`, replace the current `## Python Package Setup` section, from the heading through the dotenv block before `## Python Script Or Scheduled Job`, with this content:

````markdown
## Python Package Setup

Do these steps from your project's root folder.

### Step 1: Install The Package

```bash
uv add "ops-board-observe @ git+https://github.com/Wenjun-Mao/ops-board.git#subdirectory=packages/ops-board-observe"
```

### Step 2: Create `ops-board.yaml`

Create this file at your project root:

```text
ops-board.yaml
```

For a script, scheduled job, or worker, start with this exact file and edit the names:

```yaml
service:
  name: my-job
  namespace: my-project
  environment: prod
  owner: team-name
  version: 0.1.0

runtime:
  host: job-host
  tailscale_host: job-host.tailnet-name.ts.net

ops_board:
  otlp_endpoint: http://hp-15:4318
```

For a web/API service with a health endpoint, use the same file and add `health_url`:

```yaml
service:
  name: my-api
  namespace: my-project
  environment: prod
  owner: team-name
  version: 0.1.0

runtime:
  host: api-host
  tailscale_host: api-host.tailnet-name.ts.net

ops_board:
  otlp_endpoint: http://hp-15:4318
  health_url: http://api-host.tailnet-name.ts.net:8000/health
```

The package automatically reads `ops-board.yaml` when you run Python from the folder that contains it.

If you run Python from a different folder, point to the file explicitly:

```bash
export OPS_BOARD_CONFIG_FILE=/absolute/path/to/ops-board.yaml
```

### Step 3: Check The Config Loads

Run this from the same folder where you will start the app or job:

```bash
uv run python -c "from ops_board_observe import load_settings; print(load_settings().service_name)"
```

Expected for the job example:

```text
my-job
```

Expected for the API example:

```text
my-api
```

### Step 4: Import The Package

```python
from ops_board_observe import bootstrap_observability, observe
```
````

- [ ] **Step 2: Make the script/job section explicitly depend on `ops-board.yaml`**

In `docs/onboarding/human-guide.md`, replace the first paragraph under `## Python Script Or Scheduled Job` with:

```markdown
After `ops-board.yaml` exists and the sanity check prints `my-job`, add observability near the job entrypoint.
```

Keep the code block, but ensure it is exactly:

```python
from ops_board_observe import bootstrap_observability, observe

bootstrap_observability()


@observe("my-job.run")
def run_job() -> dict[str, str]:
    return {"status": "success"}
```

- [ ] **Step 3: Make the API section explicitly depend on API config**

In `docs/onboarding/human-guide.md`, replace the sentence:

```markdown
For the API example below, use `OPS_BOARD_SERVICE_NAME=my-api` in the same minimum config block before starting the service.
```

with:

```markdown
For the API example below, use the API `ops-board.yaml` example from Step 2 and confirm the sanity check prints `my-api`.
```

- [ ] **Step 4: Reframe Dockerized App as the environment-variable alternative**

In `docs/onboarding/human-guide.md`, replace `## Dockerized App` with:

````markdown
## Dockerized App Or CI

For Docker Compose, CI, or a process manager, environment variables are usually easier than mounting `ops-board.yaml`.

Use the same values as the YAML examples:

```yaml
environment:
  OPS_BOARD_SERVICE_NAME: my-api
  OPS_BOARD_SERVICE_NAMESPACE: my-project
  OPS_BOARD_ENVIRONMENT: prod
  OPS_BOARD_OWNER: team-name
  OPS_BOARD_VERSION: 0.1.0
  OPS_BOARD_RUNTIME_HOST: api-host
  OPS_BOARD_TAILSCALE_HOST: api-host.tailnet-name.ts.net
  OPS_BOARD_OTLP_ENDPOINT: http://hp-15:4318
  OPS_BOARD_HEALTH_URL: http://api-host.tailnet-name.ts.net:8000/health
```

Use Docker logs plus SigNoz traces as the first debugging layer.
````

- [ ] **Step 5: Strengthen remote machine checklist**

In `docs/onboarding/human-guide.md`, replace the numbered list under `## Remote Tailscale Machine` with:

```markdown
1. Join the same tailnet as `hp-15`.
2. From the project host, confirm it can reach the Ops Board collector:

   ```bash
   curl -fsS --max-time 20 http://hp-15:13133/
   ```

3. Confirm `ops-board.yaml` uses `otlp_endpoint: http://hp-15:4318`, or confirm the process has `OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318`.
4. Run the app or job.
5. Check SigNoz from `http://hp-15:8080`.
```

- [ ] **Step 6: Verify the human guide no longer has the vague phrase**

Run:

```bash
rg -n "Before calling|minimum service identity|same minimum config block|configure `OPS_BOARD_OTLP_ENDPOINT`" docs/onboarding/human-guide.md
```

Expected: no matches.

- [ ] **Step 7: Commit human-guide rewrite**

```bash
git add docs/onboarding/human-guide.md
git commit -m "docs: make human onboarding config explicit"
```

## Task 2: Align The Codex Guide With The Same Default Path

**Files:**
- Modify: `docs/onboarding/codex-guide.md`

- [ ] **Step 1: Replace env-first Python config with YAML-first guidance**

In `docs/onboarding/codex-guide.md`, replace the `Add config through env vars:` paragraph and dotenv block, plus the current short YAML alternative, with:

````markdown
Prefer `ops-board.yaml` for first onboarding unless the target already deploys through Docker, CI, or a process manager.

Create `ops-board.yaml` at the target project root:

```yaml
service:
  name: billing-api
  namespace: billing
  environment: prod
  owner: data-team
  version: 0.1.0

runtime:
  host: billing-host
  tailscale_host: billing-host.tailnet-name.ts.net

ops_board:
  otlp_endpoint: http://hp-15:4318
  health_url: http://billing-host.tailnet-name.ts.net:8000/health
```

The package reads `ops-board.yaml` automatically when the app starts from that directory. If the app starts from another working directory, set:

```bash
export OPS_BOARD_CONFIG_FILE=/absolute/path/to/ops-board.yaml
```

For Docker Compose, CI, or a process manager, use equivalent environment variables instead:

```dotenv
OPS_BOARD_SERVICE_NAME=billing-api
OPS_BOARD_SERVICE_NAMESPACE=billing
OPS_BOARD_ENVIRONMENT=prod
OPS_BOARD_OWNER=data-team
OPS_BOARD_VERSION=0.1.0
OPS_BOARD_RUNTIME_HOST=billing-host
OPS_BOARD_TAILSCALE_HOST=billing-host.tailnet-name.ts.net
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
OPS_BOARD_HEALTH_URL=http://billing-host.tailnet-name.ts.net:8000/health
```
````

- [ ] **Step 2: Add an agent sanity check before code edits**

After the config block in `docs/onboarding/codex-guide.md`, add:

````markdown
Before editing app code, verify the package reads the intended service name:

```bash
uv run python -c "from ops_board_observe import load_settings; print(load_settings().service_name)"
```

Expected for the example above:

```text
billing-api
```
````

- [ ] **Step 3: Make validation commands concrete about config source**

In `docs/onboarding/codex-guide.md`, under `## Validation Commands`, add this before `Run project tests:`:

````markdown
If validation runs from a directory that does not contain `ops-board.yaml`, export the config path first:

```bash
export OPS_BOARD_CONFIG_FILE=/absolute/path/to/ops-board.yaml
```
````

- [ ] **Step 4: Verify stale or ambiguous agent wording is gone**

Run:

```bash
rg -n "Add config through env vars|Alternatively, create `ops-board.yaml`|copy or adapt|shared\\.ops_observe|minimum config" docs/onboarding/codex-guide.md
```

Expected: no matches.

- [ ] **Step 5: Commit Codex guide alignment**

```bash
git add docs/onboarding/codex-guide.md
git commit -m "docs: align codex onboarding with yaml-first path"
```

## Task 3: Make The Contract Name The Config Channels

**Files:**
- Modify: `docs/onboarding/onboarding-contract.md`

- [ ] **Step 1: Add a config channel table**

In `docs/onboarding/onboarding-contract.md`, after the `## App Config Shape` YAML example and before `## Python Environment Variable Conventions`, add:

````markdown
## Python Config Channels

Use one config channel first. Do not duplicate the same field in multiple places unless you are intentionally overriding it.

| Channel | Use when | How `ops-board-observe` finds it |
|---------|----------|-----------------------------------|
| `ops-board.yaml` | First onboarding, local project runs, scripts, scheduled jobs | Automatically from the current working directory, or through `OPS_BOARD_CONFIG_FILE` |
| `OPS_BOARD_*` environment variables | Docker Compose, CI, systemd, process managers | The process environment |
| Docker secret files | Deployed values that should not appear in env or tracked files | `OPS_BOARD_SECRETS_DIR`, or `/run/secrets` by default |

For a teammate onboarding a Python project by hand, `ops-board.yaml` is the default path. Environment variables are the deployment override path.
````

- [ ] **Step 2: Update environment variable section to say alternative**

In `docs/onboarding/onboarding-contract.md`, replace:

```markdown
Python projects using the v1 package use the `OPS_BOARD_` prefix:
```

with:

```markdown
When a project uses environment variables instead of `ops-board.yaml`, it uses the `OPS_BOARD_` prefix:
```

- [ ] **Step 3: Clarify precedence with a concrete example**

After the precedence list in `docs/onboarding/onboarding-contract.md`, add:

````markdown
Example: if `ops-board.yaml` says `service.name: billing-api` but the process environment has `OPS_BOARD_SERVICE_NAME=billing-api-worker`, the package uses `billing-api-worker`.
````

- [ ] **Step 4: Verify contract wording supports the default path**

Run:

```bash
rg -n "Python Config Channels|ops-board.yaml is the default path|environment variables instead of `ops-board.yaml`|billing-api-worker" docs/onboarding/onboarding-contract.md
```

Expected: all four phrases are present.

- [ ] **Step 5: Commit contract clarification**

```bash
git add docs/onboarding/onboarding-contract.md
git commit -m "docs: define onboarding config channels"
```

## Task 4: Align Playground Docs Without Making Them The Colleague Path

**Files:**
- Modify: `examples/onboarding/README.md`
- Modify: `examples/onboarding/dummy-api/README.md`
- Modify: `examples/onboarding/dummy-job/README.md`

- [ ] **Step 1: Explain why the playground exports `OPS_BOARD_CONFIG_FILE`**

In `examples/onboarding/README.md`, after the paragraph that says the playground consumes `ops-board-observe`, add:

````markdown
The playground uses `examples/onboarding/config/ops-board.example.yaml` instead of a project-root `ops-board.yaml` because the dummy API and dummy job live inside this repo. Real projects should create `ops-board.yaml` at their own project root, as shown in `docs/onboarding/human-guide.md`.
````

- [ ] **Step 2: Update dummy job local run wording**

In `examples/onboarding/dummy-job/README.md`, replace the paragraph under `## Run Locally` with:

````markdown
From the repo root, point the package at the playground config file:
````

Keep the existing command block:

```bash
export OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-job python examples/onboarding/dummy-job/job.py
```

- [ ] **Step 3: Update dummy API local run wording**

In `examples/onboarding/dummy-api/README.md`, replace the paragraph under `## Run Locally` with:

````markdown
From the repo root, point the package at the playground config file:
````

Keep the existing command block:

```bash
export OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-api uvicorn app:app --app-dir examples/onboarding/dummy-api --host 0.0.0.0 --port 8000
```

- [ ] **Step 4: Verify playground docs do not teach copied helper setup**

Run:

```bash
rg -n "copy or adapt|shared\\.ops_observe|manual dependency|real projects should create `ops-board.yaml`|playground config file" examples/onboarding -g "*.md"
```

Expected:

```text
examples/onboarding\README.md contains: Real projects should create `ops-board.yaml` at their own project root
examples/onboarding\dummy-api\README.md contains: From the repo root, point the package at the playground config file:
examples/onboarding\dummy-job\README.md contains: From the repo root, point the package at the playground config file:
```

No `copy or adapt`, `shared.ops_observe`, or `manual dependency` hits.

- [ ] **Step 5: Commit playground docs**

```bash
git add examples/onboarding/README.md examples/onboarding/dummy-api/README.md examples/onboarding/dummy-job/README.md
git commit -m "docs: clarify playground config path"
```

## Task 5: Full Verification And Final Push

**Files:**
- Verify all changed docs and existing package/playground behavior.

- [ ] **Step 1: Run docs ambiguity scan**

Run:

```bash
rg -n "Before calling|minimum service identity|same minimum config block|Add config through env vars|Alternatively, create `ops-board.yaml`|copy or adapt|shared\\.ops_observe|manually install" docs/onboarding examples/onboarding docs/monitoring -g "*.md"
```

Expected: no matches.

- [ ] **Step 2: Run endpoint scope scan**

Run:

```bash
rg -n "localhost:4318|localhost:8000|localhost:18080|hp-15:4318|OPS_BOARD_CONFIG_FILE|ops-board.yaml" docs/onboarding examples/onboarding docs/monitoring -g "*.md"
```

Expected:

- `localhost:4318` appears only with text saying it is for code running directly on `hp-15` or playground-local checks.
- `localhost:8000` and `localhost:18080` appear only in playground-local sections.
- `hp-15:4318` appears as the default remote OTLP endpoint.
- `OPS_BOARD_CONFIG_FILE` appears where the docs explain explicit config-file selection.
- `ops-board.yaml` appears as the human-guide default path.

- [ ] **Step 3: Run package tests**

```bash
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests -q
```

Expected: `37 passed`.

- [ ] **Step 4: Run playground tests**

```bash
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -q
```

Expected: `9 passed`.

- [ ] **Step 5: Run linter and compose validation**

```bash
uvx ruff check packages/ops-board-observe examples/onboarding
docker compose -f examples/onboarding/compose.yaml config --quiet
git diff --check
```

Expected:

- Ruff reports `All checks passed!`.
- Compose config exits 0.
- `git diff --check` exits 0.

- [ ] **Step 6: Run a docs-only self-review**

Read the rendered flow in this order:

```text
docs/onboarding/human-guide.md
docs/onboarding/codex-guide.md
docs/onboarding/onboarding-contract.md
examples/onboarding/README.md
examples/onboarding/dummy-api/README.md
examples/onboarding/dummy-job/README.md
```

Confirm these statements are true:

- A colleague can follow the human guide without knowing what `pydantic-settings` is.
- The first config action is "create `ops-board.yaml` at your project root."
- The guide explains when `OPS_BOARD_CONFIG_FILE` is needed.
- Docker/CI env vars are presented as an alternative, not the beginner default.
- Playground docs are clearly repo-local examples.
- No active doc tells a colleague to copy `shared.ops_observe`.

- [ ] **Step 7: Commit verification fixes if needed**

If verification finds a small docs issue, fix it and commit:

```bash
git add docs/onboarding examples/onboarding
git commit -m "docs: polish onboarding guide clarity"
```

If verification finds no issue, skip this step.

- [ ] **Step 8: Push main**

```bash
git status --short --branch
git push origin main
```

Expected: `main` pushes successfully and `git status --short --branch` is clean afterward.

## Self-Review

Spec coverage:

- Human guide default path is explicit: Task 1.
- Codex guide follows the same default path: Task 2.
- Contract names config channels and precedence: Task 3.
- Playground docs explain why they use `OPS_BOARD_CONFIG_FILE`: Task 4.
- Stale helper-copy and vague wording scans are included: Task 5.

Ambiguity scan:

- No unfinished-marker instructions.
- No "configure this" step without a concrete file, command, or replacement.
- Example service names are concrete: `my-job`, `my-api`, and `billing-api`.

Type and naming consistency:

- Package distribution name is `ops-board-observe`.
- Python import name is `ops_board_observe`.
- Config file is `ops-board.yaml`.
- Explicit config file env var is `OPS_BOARD_CONFIG_FILE`.
- Default remote OTLP endpoint is `http://hp-15:4318`.

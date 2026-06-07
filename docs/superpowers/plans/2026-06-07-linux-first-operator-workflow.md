# Linux-First Operator Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Linux-first operator scripts and docs, then validate Ops Board on `HP-15`.

**Architecture:** Keep the existing Compose layout and Python Uptime Kuma bootstrap helper. Add Bash entrypoints in `scripts/`, with shared shell helpers in `scripts/lib/ops-board.sh` to avoid duplicated Compose/env/path behavior. Keep PowerShell files as legacy compatibility, but document Linux as the default path.

**Tech Stack:** Bash 5, Docker Compose, `uv`, Python 3.12, curl, git, Tailscale/SSH to `HP-15`.

---

## File Structure

- Create: `.gitattributes` - force LF line endings for shell scripts.
- Create: `scripts/lib/ops-board.sh` - shared Bash functions for repo root discovery, Compose argument construction, env-file editing, command checks, and URL encoding.
- Create: `scripts/init-local-config.sh` - Linux-first local config and secret generator.
- Create: `scripts/bootstrap-uptime-kuma.sh` - Linux wrapper for the existing Python/`uv` Uptime Kuma bootstrap helper.
- Create: `scripts/status.sh` - Linux Compose status helper.
- Create: `scripts/update-stack.sh` - Linux Compose pull/up/status helper.
- Create: `scripts/smoke-day1.sh` - Linux Day-1 acceptance smoke.
- Create: `scripts/tests/test-linux-operator-scripts.sh` - Bash regression tests for Linux scripts.
- Modify: `scripts/backup.ps1` - include Linux scripts in the non-secret backup allowlist.
- Modify: `scripts/restore.ps1` - restore Linux scripts from backup archives.
- Modify: `README.md` - make Linux commands the default.
- Modify: `scripts/README.md` - document Linux scripts first and PowerShell as legacy compatibility.
- Modify: `docs/monitoring/ops-board-user-manual.md` - switch setup/smoke examples to Linux-first commands and explain host URLs.
- Modify: `docs/onboarding/codex-guide.md` - switch Codex workflow snippets to Linux-first commands.
- Modify: `docs/onboarding/human-guide.md` - switch human onboarding snippets to Linux-first commands.
- Modify: `stacks/uptime-kuma/docs/monitors.md` - switch bootstrap docs to Linux-first commands.

## Task 1: Add LF Guard And RED Test Harness

**Files:**
- Create: `.gitattributes`
- Create: `scripts/tests/test-linux-operator-scripts.sh`

- [ ] **Step 1: Create `.gitattributes`**

```gitattributes
*.sh text eol=lf
scripts/lib/*.sh text eol=lf
scripts/tests/*.sh text eol=lf
```

- [ ] **Step 2: Create the initial failing Linux script test**

Create `scripts/tests/test-linux-operator-scripts.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
work_root=""

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_file() {
  [[ -f "$1" ]] || fail "Expected file: $1"
}

assert_executable() {
  [[ -x "$1" ]] || fail "Expected executable script: $1"
}

assert_contains() {
  local path="$1"
  local expected="$2"
  grep -Fq "$expected" "$path" || fail "Expected $path to contain: $expected"
}

assert_not_contains_crlf() {
  local path="$1"
  if grep -Iq . "$path" && grep -q $'\r' "$path"; then
    fail "CRLF detected in $path"
  fi
}

assert_env_value() {
  local path="$1"
  local key="$2"
  local expected="$3"
  local actual
  actual="$(grep -E "^${key}=" "$path" | tail -1 | cut -d= -f2-)"
  [[ "$actual" == "$expected" ]] || fail "Expected $key=$expected in $path, got $actual"
}

copy_repo_to_temp() {
  work_root="$(mktemp -d)"
  tar \
    --exclude='.git' \
    --exclude='temp' \
    --exclude='.venv' \
    --exclude='.pytest_cache' \
    -C "$repo_root" \
    -cf - . | tar -C "$work_root" -xf -
  printf '%s\n' "$work_root"
}

cleanup() {
  if [[ -n "${work_root:-}" && -d "$work_root" ]]; then
    rm -rf "$work_root"
  fi
}
trap cleanup EXIT

test_scripts_exist_and_parse() {
  local scripts=(
    scripts/init-local-config.sh
    scripts/bootstrap-uptime-kuma.sh
    scripts/status.sh
    scripts/update-stack.sh
    scripts/smoke-day1.sh
  )

  for script in "${scripts[@]}"; do
    assert_file "$repo_root/$script"
    assert_executable "$repo_root/$script"
    assert_not_contains_crlf "$repo_root/$script"
    bash -n "$repo_root/$script"
  done

  assert_file "$repo_root/scripts/lib/ops-board.sh"
  assert_not_contains_crlf "$repo_root/scripts/lib/ops-board.sh"
  bash -n "$repo_root/scripts/lib/ops-board.sh"
}

test_init_local_config_generates_hp15_config() {
  local temp_repo
  temp_repo="$(copy_repo_to_temp)"

  (cd "$temp_repo" && ./scripts/init-local-config.sh --host hp-15)

  assert_file "$temp_repo/.env"
  assert_file "$temp_repo/stacks/plane/plane.env"
  assert_file "$temp_repo/secrets/signoz_jwt_secret"
  assert_file "$temp_repo/secrets/uptime_kuma_admin_password"
  assert_file "$temp_repo/secrets/plane_secret_key"
  assert_file "$temp_repo/secrets/plane_postgres_password"
  assert_file "$temp_repo/secrets/plane_rabbitmq_password"
  assert_file "$temp_repo/secrets/plane_minio_password"

  assert_env_value "$temp_repo/.env" "OPS_BOARD_TAILSCALE_HOSTNAME" "hp-15"
  assert_env_value "$temp_repo/.env" "OPS_BOARD_BACKUP_ROOT" "$HOME/ops-board-backups"
  assert_env_value "$temp_repo/.env" "HOMEPAGE_PUBLIC_URL" "http://hp-15:3000"
  assert_env_value "$temp_repo/.env" "UPTIME_KUMA_PUBLIC_URL" "http://hp-15:3001"
  assert_env_value "$temp_repo/.env" "SIGNOZ_PUBLIC_URL" "http://hp-15:8080"
  assert_env_value "$temp_repo/.env" "PLANE_PUBLIC_URL" "http://hp-15:8082"
  assert_env_value "$temp_repo/.env" "PLANE_WEB_URL" "http://hp-15:8082"
  assert_contains "$temp_repo/.env" "HOMEPAGE_ALLOWED_HOSTS=localhost:3000,127.0.0.1:3000,hp-15:3000"

  assert_env_value "$temp_repo/stacks/plane/plane.env" "APP_DOMAIN" "hp-15"
  assert_env_value "$temp_repo/stacks/plane/plane.env" "WEB_URL" "http://hp-15:8082"
  assert_env_value "$temp_repo/stacks/plane/plane.env" "CORS_ALLOWED_ORIGINS" "http://hp-15:8082"
}

test_init_local_config_keeps_and_rotates_secrets() {
  local temp_repo
  temp_repo="$(copy_repo_to_temp)"

  (cd "$temp_repo" && ./scripts/init-local-config.sh --host hp-15)
  local before
  before="$(sha256sum "$temp_repo/secrets/signoz_jwt_secret" | cut -d' ' -f1)"

  (cd "$temp_repo" && ./scripts/init-local-config.sh --host hp-15)
  local after_keep
  after_keep="$(sha256sum "$temp_repo/secrets/signoz_jwt_secret" | cut -d' ' -f1)"
  [[ "$before" == "$after_keep" ]] || fail "Secret rotated without --force"

  (cd "$temp_repo" && ./scripts/init-local-config.sh --host hp-15 --force)
  local after_force
  after_force="$(sha256sum "$temp_repo/secrets/signoz_jwt_secret" | cut -d' ' -f1)"
  [[ "$before" != "$after_force" ]] || fail "Secret did not rotate with --force"
}

test_compose_wrappers_support_help_and_dry_run() {
  "$repo_root/scripts/bootstrap-uptime-kuma.sh" --help | grep -Fq "Usage:"
  "$repo_root/scripts/status.sh" --help | grep -Fq "Usage:"
  "$repo_root/scripts/update-stack.sh" --help | grep -Fq "Usage:"
  "$repo_root/scripts/smoke-day1.sh" --help | grep -Fq "Usage:"

  local status_output
  status_output="$("$repo_root/scripts/status.sh" --stack uptime-kuma --dry-run)"
  grep -Fq "stacks/uptime-kuma/compose.yaml" <<<"$status_output" || fail "status dry-run did not target uptime-kuma compose file"
  grep -Fq "ps -a" <<<"$status_output" || fail "status dry-run did not include ps -a"

  local update_output
  update_output="$("$repo_root/scripts/update-stack.sh" --stack homepage --remove-orphans --dry-run)"
  grep -Fq "stacks/homepage/compose.yaml" <<<"$update_output" || fail "update dry-run did not target homepage compose file"
  grep -Fq -- "--remove-orphans" <<<"$update_output" || fail "update dry-run did not include --remove-orphans"

  local bootstrap_output
  bootstrap_output="$("$repo_root/scripts/bootstrap-uptime-kuma.sh" --dry-run)"
  grep -Fq "uv run --project" <<<"$bootstrap_output" || fail "bootstrap dry-run did not include uv"
}

test_smoke_supports_help_and_dry_run() {
  local output
  output="$("$repo_root/scripts/smoke-day1.sh" --skip-onboarding --skip-telemetry-query --dry-run)"
  grep -Fq "docker compose" <<<"$output" || fail "smoke dry-run did not include compose validation"
  grep -Fq "http://localhost:3000" <<<"$output" || fail "smoke dry-run did not include Homepage check"
  grep -Fq "bootstrap-uptime-kuma.sh" <<<"$output" || fail "smoke dry-run did not include Uptime Kuma bootstrap"
}

test_scripts_exist_and_parse
test_init_local_config_generates_hp15_config
test_init_local_config_keeps_and_rotates_secrets
test_compose_wrappers_support_help_and_dry_run
test_smoke_supports_help_and_dry_run

printf 'Linux operator script tests passed.\n'
```

- [ ] **Step 3: Run the test and verify RED**

Run:

```bash
bash scripts/tests/test-linux-operator-scripts.sh
```

Expected: FAIL with `Expected file: ... scripts/init-local-config.sh` or `Expected executable script: ... scripts/init-local-config.sh`.

## Task 2: Add Shared Shell Helpers And Init Script

**Files:**
- Create: `scripts/lib/ops-board.sh`
- Create: `scripts/init-local-config.sh`
- Test: `scripts/tests/test-linux-operator-scripts.sh`

- [ ] **Step 1: Create `scripts/lib/ops-board.sh`**

```bash
#!/usr/bin/env bash

ops_die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

ops_repo_root_from_script_dir() {
  local script_dir="$1"
  cd "$script_dir/.." >/dev/null 2>&1 && pwd
}

ops_require_cmd() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || ops_die "Missing required command: $command_name"
}

ops_print_command() {
  printf '%q ' "$@"
  printf '\n'
}

ops_urlencode() {
  local value="$1"
  python3 - "$value" <<'PY'
import sys
from urllib.parse import quote

print(quote(sys.argv[1], safe=""))
PY
}

ops_set_env_value() {
  local path="$1"
  local key="$2"
  local value="$3"

  python3 - "$path" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
prefix = f"{key}="

lines = path.read_text(encoding="utf-8").splitlines()
for index, line in enumerate(lines):
    if line.startswith(prefix):
        lines[index] = f"{prefix}{value}"
        break
else:
    lines.append(f"{prefix}{value}")

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

ops_build_compose_args() {
  local repo_root="$1"
  local stack="$2"
  OPS_COMPOSE_ARGS=(compose)

  local root_env="$repo_root/.env"
  if [[ -f "$root_env" ]]; then
    OPS_COMPOSE_ARGS+=(--env-file "$root_env")
  fi

  local compose_file
  if [[ "$stack" == "ops-board" ]]; then
    compose_file="$repo_root/compose.yaml"
  else
    compose_file="$repo_root/stacks/$stack/compose.yaml"
    local stack_dir="$repo_root/stacks/$stack"
    local stack_env
    for stack_env in "$stack_dir/.env" "$stack_dir/$stack.env"; do
      if [[ -f "$stack_env" ]]; then
        OPS_COMPOSE_ARGS+=(--env-file "$stack_env")
      fi
    done
  fi

  [[ -f "$compose_file" ]] || ops_die "Compose file not found for stack '$stack': $compose_file"
  OPS_COMPOSE_ARGS+=(-f "$compose_file")
}
```

- [ ] **Step 2: Create `scripts/init-local-config.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/ops-board.sh
source "$script_dir/lib/ops-board.sh"

repo_root="$(ops_repo_root_from_script_dir "$script_dir")"
force=0
host_name="localhost"

usage() {
  cat <<'EOF'
Usage: ./scripts/init-local-config.sh [--host HOSTNAME] [--force]

Creates ignored local runtime config:
  .env
  secrets/signoz_jwt_secret
  secrets/uptime_kuma_admin_password
  secrets/plane_secret_key
  secrets/plane_postgres_password
  secrets/plane_rabbitmq_password
  secrets/plane_minio_password
  stacks/plane/plane.env

Options:
  --host HOSTNAME  Public host used in generated URLs. Default: localhost.
  --force          Recreate .env, rotate secrets, and recreate Plane env.
  -h, --help       Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      [[ $# -ge 2 ]] || ops_die "Missing value for --host"
      host_name="$2"
      shift 2
      ;;
    --force)
      force=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ops_die "Unknown argument: $1"
      ;;
  esac
done

ops_require_cmd python3

env_example="$repo_root/.env.example"
env_file="$repo_root/.env"
secrets_dir="$repo_root/secrets"
plane_stack_dir="$repo_root/stacks/plane"
plane_env_example="$plane_stack_dir/plane.env.example"
plane_env_file="$plane_stack_dir/plane.env"

[[ -f "$env_example" ]] || ops_die "Missing .env.example at $env_example"
[[ -f "$plane_env_example" ]] || ops_die "Missing Plane env example at $plane_env_example"

new_secret_value() {
  python3 - <<'PY'
import base64
import os

print(base64.b64encode(os.urandom(48)).decode("ascii"), end="")
PY
}

write_secret_file() {
  local path="$1"
  local label="$2"

  if [[ ! -f "$path" || "$force" -eq 1 ]]; then
    new_secret_value > "$path"
    chmod 600 "$path"
    printf 'Wrote Docker secret: %s\n' "$label"
  else
    printf 'Keeping existing Docker secret: %s. Use --force to rotate it.\n' "$label"
  fi
}

secret_text() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

print(Path(sys.argv[1]).read_text(encoding="utf-8").strip(), end="")
PY
}

if [[ ! -f "$env_file" || "$force" -eq 1 ]]; then
  cp "$env_example" "$env_file"
  printf 'Wrote local .env from .env.example\n'
else
  printf 'Keeping existing .env. Use --force to recreate it from .env.example.\n'
fi

mkdir -p "$secrets_dir"

write_secret_file "$secrets_dir/signoz_jwt_secret" "secrets/signoz_jwt_secret"
write_secret_file "$secrets_dir/uptime_kuma_admin_password" "secrets/uptime_kuma_admin_password"
write_secret_file "$secrets_dir/plane_secret_key" "secrets/plane_secret_key"
write_secret_file "$secrets_dir/plane_postgres_password" "secrets/plane_postgres_password"
write_secret_file "$secrets_dir/plane_rabbitmq_password" "secrets/plane_rabbitmq_password"
write_secret_file "$secrets_dir/plane_minio_password" "secrets/plane_minio_password"

ops_set_env_value "$env_file" "OPS_BOARD_TAILSCALE_HOSTNAME" "$host_name"
ops_set_env_value "$env_file" "OPS_BOARD_BACKUP_ROOT" "$HOME/ops-board-backups"
ops_set_env_value "$env_file" "SIGNOZ_PUBLIC_URL" "http://$host_name:8080"
ops_set_env_value "$env_file" "UPTIME_KUMA_PUBLIC_URL" "http://$host_name:3001"
ops_set_env_value "$env_file" "HOMEPAGE_PUBLIC_URL" "http://$host_name:3000"
ops_set_env_value "$env_file" "HOMEPAGE_ALLOWED_HOSTS" "localhost:3000,127.0.0.1:3000,$host_name:3000"
ops_set_env_value "$env_file" "PLANE_PUBLIC_URL" "http://$host_name:8082"
ops_set_env_value "$env_file" "PLANE_WEB_URL" "http://$host_name:8082"

if [[ -f "$plane_env_file" && "$force" -eq 0 ]]; then
  printf 'Keeping existing Plane env: stacks/plane/plane.env. Use --force to recreate it.\n'
else
  cp "$plane_env_example" "$plane_env_file"

  secret_key="$(secret_text "$secrets_dir/plane_secret_key")"
  postgres_password="$(secret_text "$secrets_dir/plane_postgres_password")"
  rabbitmq_password="$(secret_text "$secrets_dir/plane_rabbitmq_password")"
  minio_password="$(secret_text "$secrets_dir/plane_minio_password")"
  postgres_password_encoded="$(ops_urlencode "$postgres_password")"
  rabbitmq_password_encoded="$(ops_urlencode "$rabbitmq_password")"

  ops_set_env_value "$plane_env_file" "APP_DOMAIN" "$host_name"
  ops_set_env_value "$plane_env_file" "APP_RELEASE" "v1.3.1"
  ops_set_env_value "$plane_env_file" "LISTEN_HTTP_PORT" "8082"
  ops_set_env_value "$plane_env_file" "LISTEN_HTTPS_PORT" "8443"
  ops_set_env_value "$plane_env_file" "WEB_URL" "http://$host_name:8082"
  ops_set_env_value "$plane_env_file" "PLANE_DEBUG" "0"
  ops_set_env_value "$plane_env_file" "CORS_ALLOWED_ORIGINS" "http://$host_name:8082"
  ops_set_env_value "$plane_env_file" "POSTGRES_PASSWORD" "$postgres_password"
  ops_set_env_value "$plane_env_file" "DATABASE_URL" "postgresql://plane:$postgres_password_encoded@plane-db/plane"
  ops_set_env_value "$plane_env_file" "RABBITMQ_PASSWORD" "$rabbitmq_password"
  ops_set_env_value "$plane_env_file" "AMQP_URL" "amqp://plane:$rabbitmq_password_encoded@plane-mq:5672/plane"
  ops_set_env_value "$plane_env_file" "SECRET_KEY" "$secret_key"
  ops_set_env_value "$plane_env_file" "LIVE_SERVER_SECRET_KEY" "$secret_key"
  ops_set_env_value "$plane_env_file" "AWS_SECRET_ACCESS_KEY" "$minio_password"

  printf 'Wrote local Plane env: stacks/plane/plane.env\n'
fi

printf 'Local config is ready.\n'
printf 'Start Ops Board with:\n'
printf 'docker compose --env-file .env -f compose.yaml up -d\n'
```

- [ ] **Step 3: Mark shell scripts executable**

Run:

```bash
chmod +x scripts/init-local-config.sh
```

- [ ] **Step 4: Run tests and confirm remaining RED failures are expected**

Run:

```bash
bash scripts/tests/test-linux-operator-scripts.sh
```

Expected: FAIL for missing `scripts/bootstrap-uptime-kuma.sh`. The init config assertions should not be the failing layer.

## Task 3: Add Compose Wrapper Scripts

**Files:**
- Create: `scripts/bootstrap-uptime-kuma.sh`
- Create: `scripts/status.sh`
- Create: `scripts/update-stack.sh`
- Test: `scripts/tests/test-linux-operator-scripts.sh`

- [ ] **Step 1: Create `scripts/bootstrap-uptime-kuma.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/ops-board.sh
source "$script_dir/lib/ops-board.sh"

repo_root="$(ops_repo_root_from_script_dir "$script_dir")"
config_path=""
skip_optional=0
dry_run=0
pass_help=0

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-uptime-kuma.sh [--config PATH] [--skip-optional] [--dry-run]

Runs the Python Uptime Kuma bootstrap helper through uv.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      [[ $# -ge 2 ]] || ops_die "Missing value for --config"
      config_path="$2"
      shift 2
      ;;
    --skip-optional)
      skip_optional=1
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      pass_help=1
      shift
      ;;
    *)
      ops_die "Unknown argument: $1"
      ;;
  esac
done

bootstrap_project="$repo_root/stacks/uptime-kuma/bootstrap"
bootstrap_script="$bootstrap_project/bootstrap.py"
[[ -f "$bootstrap_script" ]] || ops_die "Missing Uptime Kuma bootstrap helper: $bootstrap_script"

cmd=(uv run --project "$bootstrap_project" python "$bootstrap_script")
if [[ "$pass_help" -eq 1 ]]; then
  cmd+=(--help)
else
  if [[ -n "$config_path" ]]; then
    cmd+=(--config "$config_path")
  fi
  if [[ "$skip_optional" -eq 1 ]]; then
    cmd+=(--skip-optional)
  fi
fi

if [[ "$dry_run" -eq 1 ]]; then
  ops_print_command "${cmd[@]}"
  exit 0
fi

cd "$repo_root"
"${cmd[@]}"
```

- [ ] **Step 2: Create `scripts/status.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/ops-board.sh
source "$script_dir/lib/ops-board.sh"

repo_root="$(ops_repo_root_from_script_dir "$script_dir")"
stack="ops-board"
dry_run=0

usage() {
  cat <<'EOF'
Usage: ./scripts/status.sh [--stack STACK] [--dry-run]

Shows Docker Compose status for the root board or a single stack.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack)
      [[ $# -ge 2 ]] || ops_die "Missing value for --stack"
      stack="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ops_die "Unknown argument: $1"
      ;;
  esac
done

ops_build_compose_args "$repo_root" "$stack"
cmd=(docker "${OPS_COMPOSE_ARGS[@]}" ps -a)

if [[ "$dry_run" -eq 1 ]]; then
  ops_print_command "${cmd[@]}"
  exit 0
fi

"${cmd[@]}"
```

- [ ] **Step 3: Create `scripts/update-stack.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/ops-board.sh
source "$script_dir/lib/ops-board.sh"

repo_root="$(ops_repo_root_from_script_dir "$script_dir")"
stack="ops-board"
remove_orphans=0
dry_run=0

usage() {
  cat <<'EOF'
Usage: ./scripts/update-stack.sh [--stack STACK] [--remove-orphans] [--dry-run]

Pulls images for a stack, runs docker compose up -d, and prints status.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack)
      [[ $# -ge 2 ]] || ops_die "Missing value for --stack"
      stack="$2"
      shift 2
      ;;
    --remove-orphans)
      remove_orphans=1
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ops_die "Unknown argument: $1"
      ;;
  esac
done

ops_build_compose_args "$repo_root" "$stack"
pull_cmd=(docker "${OPS_COMPOSE_ARGS[@]}" pull)
up_cmd=(docker "${OPS_COMPOSE_ARGS[@]}" up -d)
if [[ "$remove_orphans" -eq 1 ]]; then
  up_cmd+=(--remove-orphans)
fi
ps_cmd=(docker "${OPS_COMPOSE_ARGS[@]}" ps)

if [[ "$dry_run" -eq 1 ]]; then
  ops_print_command "${pull_cmd[@]}"
  ops_print_command "${up_cmd[@]}"
  ops_print_command "${ps_cmd[@]}"
  exit 0
fi

"${pull_cmd[@]}"
"${up_cmd[@]}"
"${ps_cmd[@]}"
```

- [ ] **Step 4: Mark scripts executable**

```bash
chmod +x scripts/bootstrap-uptime-kuma.sh scripts/status.sh scripts/update-stack.sh
```

- [ ] **Step 5: Run tests and confirm remaining RED failure is expected**

Run:

```bash
bash scripts/tests/test-linux-operator-scripts.sh
```

Expected: FAIL for missing `scripts/smoke-day1.sh`.

## Task 4: Add Linux Day-1 Smoke Script

**Files:**
- Create: `scripts/smoke-day1.sh`
- Test: `scripts/tests/test-linux-operator-scripts.sh`

- [ ] **Step 1: Create `scripts/smoke-day1.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/ops-board.sh
source "$script_dir/lib/ops-board.sh"

repo_root="$(ops_repo_root_from_script_dir "$script_dir")"
skip_onboarding=0
skip_telemetry_query=0
timeout_sec=20
dry_run=0

usage() {
  cat <<'EOF'
Usage: ./scripts/smoke-day1.sh [--skip-onboarding] [--skip-telemetry-query] [--timeout-sec SECONDS] [--dry-run]

Runs the repeatable Day-1 acceptance smoke after Ops Board is running.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-onboarding)
      skip_onboarding=1
      shift
      ;;
    --skip-telemetry-query)
      skip_telemetry_query=1
      shift
      ;;
    --timeout-sec)
      [[ $# -ge 2 ]] || ops_die "Missing value for --timeout-sec"
      timeout_sec="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ops_die "Unknown argument: $1"
      ;;
  esac
done

write_section() {
  printf '\n== %s ==\n' "$1"
}

run_checked() {
  local label="$1"
  shift
  printf '%s\n' "$label"
  if [[ "$dry_run" -eq 1 ]]; then
    ops_print_command "$@"
    return
  fi
  "$@"
}

test_http_endpoint() {
  local name="$1"
  local uri="$2"
  local accepted_regex="$3"

  if [[ "$dry_run" -eq 1 ]]; then
    printf 'HTTP check: %s %s accepts %s\n' "$name" "$uri" "$accepted_regex"
    return
  fi

  local status_code
  status_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "$timeout_sec" "$uri" || true)"
  if [[ ! "$status_code" =~ $accepted_regex ]]; then
    ops_die "$name returned HTTP $status_code for $uri"
  fi

  printf '%s: HTTP %s\n' "$name" "$status_code"
}

get_recent_telemetry() {
  local query
  query=$(cat <<'SQL'
SELECT serviceName, name, count()
FROM signoz_traces.signoz_index_v3
WHERE timestamp >= now() - INTERVAL 30 MINUTE
  AND serviceName IN ('dummy-api','dummy-job')
GROUP BY serviceName, name
ORDER BY serviceName, name
SQL
)
  docker exec signoz-clickhouse clickhouse-client --query "$query"
}

wait_required_telemetry() {
  local required_patterns=(
    'dummy-api[[:space:]]+dummy-api\.work'
    'dummy-api[[:space:]]+dummy-api\.expensive-lookup'
    'dummy-job[[:space:]]+dummy-job\.run'
    'dummy-job[[:space:]]+dummy-job\.process-record'
  )
  local deadline=$((SECONDS + 90))
  local output=""

  while (( SECONDS < deadline )); do
    output="$(get_recent_telemetry || true)"
    local missing=0
    local pattern
    for pattern in "${required_patterns[@]}"; do
      if [[ ! "$output" =~ $pattern ]]; then
        missing=1
      fi
    done

    if [[ "$missing" -eq 0 ]]; then
      printf 'Recent SigNoz telemetry:\n%s\n' "$output"
      return
    fi
    sleep 5
  done

  printf 'Last telemetry query output:\n%s\n' "$output"
  ops_die "Timed out waiting for required dummy-api and dummy-job telemetry."
}

cd "$repo_root"

write_section "Compose"
run_checked "Validating root Compose config" docker compose --env-file .env -f compose.yaml config --quiet

write_section "Uptime Kuma Bootstrap"
run_checked "Running idempotent Uptime Kuma bootstrap" "$repo_root/scripts/bootstrap-uptime-kuma.sh"

write_section "Local Endpoints"
test_http_endpoint "Homepage" "http://localhost:3000" '^200$'
test_http_endpoint "Uptime Kuma" "http://localhost:3001" '^(200|302)$'
test_http_endpoint "Uptime Kuma status page" "http://localhost:3001/status/ops-board" '^200$'
test_http_endpoint "SigNoz health" "http://localhost:8080/api/v1/health" '^200$'
test_http_endpoint "SigNoz collector" "http://localhost:13133/" '^200$'
test_http_endpoint "Plane" "http://localhost:8082" '^(200|302|307|308)$'

if [[ "$skip_onboarding" -eq 0 ]]; then
  write_section "Onboarding Playground"
  run_checked "Starting dummy API" docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
  test_http_endpoint "Dummy API health" "http://localhost:18080/health" '^200$'
  test_http_endpoint "Dummy API work" "http://localhost:18080/work/demo" '^200$'
  run_checked "Running dummy job" docker compose -f examples/onboarding/compose.yaml run --rm dummy-job

  if [[ "$skip_telemetry_query" -eq 0 ]]; then
    write_section "SigNoz Telemetry"
    if [[ "$dry_run" -eq 1 ]]; then
      printf 'Telemetry query: docker exec signoz-clickhouse clickhouse-client --query <required dummy telemetry>\n'
    else
      wait_required_telemetry
    fi
  fi
fi

printf '\nDay-1 smoke passed.\n'
```

- [ ] **Step 2: Mark script executable**

```bash
chmod +x scripts/smoke-day1.sh
```

- [ ] **Step 3: Run tests and verify GREEN**

Run:

```bash
bash scripts/tests/test-linux-operator-scripts.sh
```

Expected: PASS with `Linux operator script tests passed.`

- [ ] **Step 4: Commit Linux scripts**

```bash
git add .gitattributes scripts/lib/ops-board.sh scripts/init-local-config.sh scripts/bootstrap-uptime-kuma.sh scripts/status.sh scripts/update-stack.sh scripts/smoke-day1.sh scripts/tests/test-linux-operator-scripts.sh
git commit -m "feat: add linux operator scripts"
```

## Task 5: Update Backup/Restore Allowlists

**Files:**
- Modify: `scripts/backup.ps1`
- Modify: `scripts/restore.ps1`

- [ ] **Step 1: Add Linux scripts to `scripts/backup.ps1`**

Add these entries in `$backupItems` after `"scripts/README.md",`:

```powershell
    "scripts/lib/ops-board.sh",
    "scripts/init-local-config.sh",
    "scripts/bootstrap-uptime-kuma.sh",
    "scripts/status.sh",
    "scripts/update-stack.sh",
    "scripts/smoke-day1.sh",
    "scripts/tests/test-linux-operator-scripts.sh",
```

- [ ] **Step 2: Add Linux scripts to `scripts/restore.ps1`**

Add these entries in `$restoreItems` after `"scripts/README.md",`:

```powershell
    "scripts/lib/ops-board.sh",
    "scripts/init-local-config.sh",
    "scripts/bootstrap-uptime-kuma.sh",
    "scripts/status.sh",
    "scripts/update-stack.sh",
    "scripts/smoke-day1.sh",
    "scripts/tests/test-linux-operator-scripts.sh",
```

- [ ] **Step 3: Verify allowlists**

Run:

```powershell
Select-String -Path scripts\backup.ps1,scripts\restore.ps1 -Pattern "scripts/lib/ops-board.sh","scripts/smoke-day1.sh"
```

Expected: each pattern appears once in `scripts/backup.ps1` and once in `scripts/restore.ps1`.

- [ ] **Step 4: Run Linux script tests again**

```bash
bash scripts/tests/test-linux-operator-scripts.sh
```

Expected: PASS.

- [ ] **Step 5: Commit allowlist update**

```bash
git add scripts/backup.ps1 scripts/restore.ps1
git commit -m "chore: include linux scripts in config backups"
```

## Task 6: Update Documentation To Linux-First

**Files:**
- Modify: `README.md`
- Modify: `scripts/README.md`
- Modify: `docs/monitoring/ops-board-user-manual.md`
- Modify: `docs/onboarding/codex-guide.md`
- Modify: `docs/onboarding/human-guide.md`
- Modify: `stacks/uptime-kuma/docs/monitors.md`

- [ ] **Step 1: Replace default setup snippets**

Use Linux-first commands in setup sections:

```bash
./scripts/init-local-config.sh --host hp-15
docker compose --env-file .env -f compose.yaml up -d
./scripts/bootstrap-uptime-kuma.sh
./scripts/smoke-day1.sh
```

Keep PowerShell commands only in a short legacy compatibility note:

```markdown
The old `*.ps1` scripts remain for compatibility during the transition, but Linux `*.sh` scripts are the default operator path.
```

- [ ] **Step 2: Add host URL guidance**

Add this explanation to `README.md` and `docs/monitoring/ops-board-user-manual.md`:

```markdown
Use the Tailscale/MagicDNS hostname in `.env` for browser-facing URLs. On `HP-15`, that means URLs such as `http://hp-15:3000` and `http://hp-15:8080`. Use `localhost` only from a shell or browser running directly on the deployment host.
```

- [ ] **Step 3: Update script reference names**

Use these replacements in operator-facing docs:

```text
.\scripts\init-local-config.ps1 -> ./scripts/init-local-config.sh
.\scripts\bootstrap-uptime-kuma.ps1 -> ./scripts/bootstrap-uptime-kuma.sh
.\scripts\smoke-day1.ps1 -> ./scripts/smoke-day1.sh
.\scripts\status.ps1 -> ./scripts/status.sh
.\scripts\update-stack.ps1 -> ./scripts/update-stack.sh
-Stack -> --stack
-RemoveOrphans -> --remove-orphans
-SkipOnboarding -> --skip-onboarding
-SkipTelemetryQuery -> --skip-telemetry-query
```

- [ ] **Step 4: Preserve screenshot policy**

Add this note to `docs/monitoring/ops-board-user-manual.md` near the dashboard screenshot section:

```markdown
The committed screenshots are reference UI states. Do not recapture them solely because the runtime host changes; refresh them only when the UI state or documented workflow changes.
```

- [ ] **Step 5: Verify docs no longer present PowerShell as the default**

Run:

```powershell
rg -n "Quick Start|Fresh Local Setup|bootstrap-uptime|smoke-day1|status\\.ps1|update-stack\\.ps1|init-local-config\\.ps1" README.md scripts/README.md docs/monitoring/ops-board-user-manual.md docs/onboarding/codex-guide.md docs/onboarding/human-guide.md stacks/uptime-kuma/docs/monitors.md
```

Expected: Linux `*.sh` commands are shown first. Any remaining `*.ps1` mentions are explicitly labeled legacy compatibility.

- [ ] **Step 6: Run Linux script tests**

```bash
bash scripts/tests/test-linux-operator-scripts.sh
```

Expected: PASS.

- [ ] **Step 7: Commit docs**

```bash
git add README.md scripts/README.md docs/monitoring/ops-board-user-manual.md docs/onboarding/codex-guide.md docs/onboarding/human-guide.md stacks/uptime-kuma/docs/monitors.md
git commit -m "docs: make linux scripts the default"
```

## Task 7: Validate On HP-15

**Files:**
- Read only on local: committed repo state.
- Remote target: `HP-15:~/projects/ops-board`

- [ ] **Step 1: Push commits**

```bash
git push
```

Expected: local `main` pushes to `origin/main`.

- [ ] **Step 2: Pull on HP-15**

```powershell
ssh HP-15 'bash -lc "cd ~/projects/ops-board && git pull --ff-only"'
```

Expected: HP-15 advances to the Linux script commits.

- [ ] **Step 3: Verify HP-15 prerequisites**

```powershell
ssh HP-15 'bash -lc "cd ~/projects/ops-board && docker --version && docker compose version && uv --version && bash --version | head -1"'
```

Expected: Docker, Docker Compose, `uv`, and Bash versions print successfully.

- [ ] **Step 4: Run Linux script tests on HP-15**

```powershell
ssh HP-15 'bash -lc "cd ~/projects/ops-board && bash scripts/tests/test-linux-operator-scripts.sh"'
```

Expected: PASS with `Linux operator script tests passed.`

- [ ] **Step 5: Initialize HP-15 local config**

```powershell
ssh HP-15 'bash -lc "cd ~/projects/ops-board && ./scripts/init-local-config.sh --host hp-15"'
```

Expected: `.env`, `secrets/*`, and `stacks/plane/plane.env` are created or kept. No secret values print.

- [ ] **Step 6: Start Ops Board on HP-15**

```powershell
ssh HP-15 'bash -lc "cd ~/projects/ops-board && docker compose --env-file .env -f compose.yaml up -d"'
```

Expected: Compose starts SigNoz, Uptime Kuma, Homepage, and Plane services.

- [ ] **Step 7: Run the HP-15 Day-1 smoke**

```powershell
ssh HP-15 'bash -lc "cd ~/projects/ops-board && ./scripts/smoke-day1.sh"'
```

Expected: PASS with endpoint checks, idempotent Uptime Kuma bootstrap, dummy API/job execution, and SigNoz telemetry rows for `dummy-api` and `dummy-job`.

- [ ] **Step 8: Check Tailscale-facing URLs from this workstation**

```powershell
Invoke-WebRequest -UseBasicParsing -Uri http://hp-15:3000 -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing -Uri http://hp-15:3001/status/ops-board -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing -Uri http://hp-15:8080/api/v1/health -TimeoutSec 20
Invoke-WebRequest -UseBasicParsing -Uri http://hp-15:8082 -TimeoutSec 20 -MaximumRedirection 0
```

Expected: Homepage and status page return HTTP 200, SigNoz health returns HTTP 200, Plane returns HTTP 200/302/307/308.

- [ ] **Step 9: Final status check**

```powershell
git status --short --branch
ssh HP-15 'bash -lc "cd ~/projects/ops-board && git status --short --branch && ./scripts/status.sh"'
```

Expected: local and HP-15 repos are clean. HP-15 Compose status shows the board containers.

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
    --exclude='.env' \
    --exclude='secrets/*' \
    --exclude='stacks/*/*.env' \
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

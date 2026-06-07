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

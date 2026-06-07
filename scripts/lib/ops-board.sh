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

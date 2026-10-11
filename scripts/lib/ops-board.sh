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

# Deployment identity lives in maintenance/deployment.py. Keep shell helpers here
# limited to setup; a stack name alone must not silently switch Compose projects.

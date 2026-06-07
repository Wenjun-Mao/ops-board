#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/ops-board.sh
source "$script_dir/lib/ops-board.sh"

repo_root="$(ops_repo_root_from_script_dir "$script_dir")"
config_path=""
skip_optional=0
dry_run=0

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
      usage
      exit 0
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
if [[ -n "$config_path" ]]; then
  cmd+=(--config "$config_path")
fi
if [[ "$skip_optional" -eq 1 ]]; then
  cmd+=(--skip-optional)
fi

if [[ "$dry_run" -eq 1 ]]; then
  ops_print_command "${cmd[@]}"
  exit 0
fi

cd "$repo_root"
"${cmd[@]}"

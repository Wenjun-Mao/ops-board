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

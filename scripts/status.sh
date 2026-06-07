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

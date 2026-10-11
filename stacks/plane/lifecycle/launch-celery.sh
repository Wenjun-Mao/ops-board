#!/bin/bash
set -e

if [[ "$#" -ne 1 || ( "$1" != worker && "$1" != beat ) ]]; then
  printf 'Expected one Plane Celery role: worker or beat\n' >&2
  exit 64
fi
role="$1"
initializer_pid=""

stop_initialization() {
  local signal="$1" status="$2" attempt
  trap '' TERM INT
  # jobs covers the narrow interval between spawning the child and assigning $!.
  initializer_pid="${initializer_pid:-$(jobs -pr)}"
  if [[ -n "$initializer_pid" ]]; then
    kill "-$signal" "$initializer_pid" 2>/dev/null || true
    for ((attempt = 0; attempt < 50; attempt++)); do
      kill -0 "$initializer_pid" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "$initializer_pid" 2>/dev/null; then
      kill -KILL "$initializer_pid" 2>/dev/null || true
      status=137
    fi
    wait "$initializer_pid" 2>/dev/null || true
  fi
  exit "$status"
}
trap 'stop_initialization TERM 143' TERM
trap 'stop_initialization INT 130' INT

initialize() {
  local status
  python manage.py "$1" &
  initializer_pid=$!
  if wait "$initializer_pid"; then status=0; else status=$?; fi
  initializer_pid=""
  return "$status"
}

# Preserve upstream initialization, then give Celery Docker's PID 1 signals.
initialize wait_for_db
initialize wait_for_migrations
exec celery -A plane "$role" -l info

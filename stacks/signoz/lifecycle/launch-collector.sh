#!/bin/sh
set -eu

if [ "$#" -lt 2 ]; then
  printf 'Expected collector executable and configuration arguments\n' >&2
  exit 64
fi
collector=$1
shift
initializer_pid=

stop_initialization() {
  stop_signal=$1
  stop_status=$2
  trap '' TERM INT
  # Cover the interval between spawning our only child and assigning $!.
  initializer_pid=${initializer_pid:-$(jobs -p)}
  if [ -n "$initializer_pid" ]; then
    kill "-$stop_signal" "$initializer_pid" 2>/dev/null || true
    attempt=0
    while kill -0 "$initializer_pid" 2>/dev/null && [ "$attempt" -lt 5 ]; do
      sleep 1
      attempt=$((attempt + 1))
    done
    if kill -0 "$initializer_pid" 2>/dev/null; then
      kill -KILL "$initializer_pid" 2>/dev/null || true
      stop_status=137
    fi
    wait "$initializer_pid" 2>/dev/null || true
  fi
  exit "$stop_status"
}
trap 'stop_initialization TERM 143' TERM
trap 'stop_initialization INT 130' INT

"$collector" migrate sync check &
initializer_pid=$!
if wait "$initializer_pid"; then status=0; else status=$?; fi
initializer_pid=
[ "$status" -eq 0 ] || exit "$status"

# The collector, not a waiting shell, owns Docker's PID 1 signals.
exec "$collector" "$@"

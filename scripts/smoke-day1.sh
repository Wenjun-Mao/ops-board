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

  local status_code=""
  local deadline=$((SECONDS + timeout_sec))
  while true; do
    status_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "$timeout_sec" "$uri" || true)"
    if [[ "$status_code" =~ $accepted_regex ]]; then
      break
    fi

    if (( SECONDS >= deadline )); then
      ops_die "$name returned HTTP $status_code for $uri after ${timeout_sec}s"
    fi
    sleep 1
  done

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

# Dummy API

This example represents a Python web/API service.

It demonstrates:

- `/health` for Uptime Kuma.
- `@observe(...)` around a request handler and a key internal function.
- `tenacity` around simulated external I/O.
- OpenTelemetry export to the Ops Board SigNoz collector.

## Run Locally

From the repo root:

```powershell
$env:OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-api uvicorn app:app --app-dir examples/onboarding/dummy-api --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/health
http://localhost:8000/work/demo
```

## Run Tests

```powershell
uv run --project examples/onboarding/dummy-api pytest examples/onboarding/dummy-api/tests -v
```

## Run In Docker

```powershell
docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
```

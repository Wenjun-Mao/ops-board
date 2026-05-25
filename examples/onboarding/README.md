# Ops Board Onboarding Playground

This playground gives Ops Board a small local project to monitor before real projects are onboarded.

It covers two common shapes:

- `dummy-job`: a scheduled or script-style Python job.
- `dummy-api`: a Python web/API service with `/health`.

Both examples use `shared/ops_observe.py`, a tiny local helper that prototypes a future Python onboarding library.

## Prerequisites

From the repo root:

```powershell
.\scripts\init-local-config.ps1
docker compose --env-file .env -f compose.yaml up -d
```

Verify the collector is reachable:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:13133/ -TimeoutSec 20
```

Expected: HTTP `200`.

## Local Python Test Run

```powershell
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
```

Expected: all tests pass.

## Run The Dummy Job Locally

```powershell
$env:OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-job python examples/onboarding/dummy-job/job.py
```

Expected: the command prints a successful job summary and emits an OpenTelemetry span to SigNoz when the collector is running.

## Run The Dummy API Locally

```powershell
$env:OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-api uvicorn app:app --app-dir examples/onboarding/dummy-api --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/health
http://localhost:8000/work/demo
```

## Run With Docker Compose

```powershell
docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

Expected:

- `dummy-api` is reachable at `http://localhost:18080/health`.
- `dummy-job` exits `0`.
- SigNoz shows services named `dummy-api` and `dummy-job`.

## Tailscale Notes

When a monitored project runs on another tailnet machine, set `OPS_BOARD_OTLP_ENDPOINT` to the Ops Board host's private address:

```powershell
$env:OPS_BOARD_OTLP_ENDPOINT="http://<ops-board-tailscale-hostname>:4318"
```

## Verify In SigNoz

After calling the API and running the job, open SigNoz:

```text
http://localhost:8080
```

Look for these service names:

```text
dummy-api
dummy-job
```

Useful first checks:

- Services view includes `dummy-api` after `/work/demo` is called.
- Traces include spans named `dummy-api.work` and `dummy-api.expensive-lookup`.
- Traces include spans named `dummy-job.run` and `dummy-job.process-record`.
- Logs are present if OTLP log export is accepted by the collector.

If the project runs on another tailnet machine, set:

```dotenv
OPS_BOARD_OTLP_ENDPOINT=http://<ops-board-tailscale-hostname>:4318
```

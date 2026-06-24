# Ops Board Onboarding Playground

This playground gives Ops Board a small local project to monitor before real projects are onboarded.

It covers two common shapes:

- `dummy-job`: a scheduled or script-style Python job.
- `dummy-api`: a Python web/API service with `/health`.

The playground consumes `ops-board-observe` through a local path dependency. That keeps the demo aligned with the package colleagues install in real projects.

The playground uses `examples/onboarding/config/ops-board.example.yaml` instead of a project-root `ops-board.yaml` because the dummy API and dummy job live inside this repo; real projects should create `ops-board.yaml` at their own project root, as shown in `docs/onboarding/human-guide.md`.

## Prerequisites

From the repo root:

```bash
./scripts/init-local-config.sh --host hp-15
docker compose --env-file .env -f compose.yaml up -d
```

Verify the collector is reachable from the Ops Board host or playground-local machine:

```bash
curl --fail --show-error --silent --max-time 20 http://localhost:13133/
```

Expected: HTTP `200`.

## Local Python Test Run

```bash
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
```

Expected: all tests pass.

## Run The Dummy Job Locally

```bash
export OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-job python examples/onboarding/dummy-job/job.py
```

Expected: the command prints a successful job summary and emits an OpenTelemetry span to SigNoz when the collector is running.

## Run The Dummy API Locally

```bash
export OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-api uvicorn app:app --app-dir examples/onboarding/dummy-api --host 0.0.0.0 --port 8000
```

Open these playground-local URLs from the same machine running the dummy API:

```text
http://localhost:8000/health
http://localhost:8000/work/demo
```

## Run With Docker Compose

```bash
docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

Expected:

- `dummy-api` is reachable at `http://localhost:18080/health`.
- `dummy-job` exits `0`.
- SigNoz shows services named `dummy-api` and `dummy-job`.

## Tailscale Notes

The localhost values in this playground describe the local demo runtime. Real projects should follow `docs/onboarding/human-guide.md` and set the normal HP-15 OTLP endpoint:

```dotenv
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
```

## Verify In SigNoz

After calling the API and running the job, open SigNoz:

```text
http://hp-15:8080
```

Use `localhost:8080` only from a browser running directly on the Ops Board host.

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

If the project runs on another tailnet machine, follow `docs/onboarding/human-guide.md` and set:

```dotenv
OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318
```

## Full Verification Checklist

Run:

```bash
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -v
docker compose -f examples/onboarding/compose.yaml config --quiet
docker compose -f examples/onboarding/compose.yaml build
docker compose --env-file .env -f compose.yaml up -d
docker compose -f examples/onboarding/compose.yaml up -d dummy-api
curl --fail --show-error --silent --max-time 20 http://localhost:18080/health
curl --fail --show-error --silent --max-time 20 http://localhost:18080/work/demo
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

Expected:

- Tests pass.
- Compose config validates.
- Images build.
- Dummy API health and work endpoints respond.
- Dummy job exits successfully.
- SigNoz receives telemetry for `dummy-api` and `dummy-job`.

# Dummy Job

This example represents a scheduled script, cron job, batch import, or one-off worker.

It demonstrates:

- `bootstrap_observability(...)` for service identity and OTLP export.
- `@observe(...)` around the job run and per-record processing.
- `tenacity` around simulated external I/O.
- Structured log fields through Python logging `extra`.

## Run Locally

From the repo root, point the package at the playground config file:

```bash
export OPS_BOARD_CONFIG_FILE="examples/onboarding/config/ops-board.example.yaml"
uv run --project examples/onboarding/dummy-job python examples/onboarding/dummy-job/job.py
```

Expected: the command prints a success summary.

## Run Tests

```bash
uv run --project examples/onboarding/dummy-job pytest examples/onboarding/dummy-job/tests -v
```

## Run In Docker

```bash
docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
```

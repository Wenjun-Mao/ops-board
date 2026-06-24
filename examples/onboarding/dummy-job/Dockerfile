# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /uvx /bin/

WORKDIR /repo/examples/onboarding/dummy-job

COPY packages/ops-board-observe /repo/packages/ops-board-observe
COPY examples/onboarding/dummy-job/pyproject.toml ./pyproject.toml
COPY examples/onboarding/dummy-job/uv.lock ./uv.lock
RUN --mount=type=cache,target=/root/.cache/uv uv sync --no-dev --no-install-project

COPY examples/onboarding/dummy-job/job.py ./job.py

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "job.py"]

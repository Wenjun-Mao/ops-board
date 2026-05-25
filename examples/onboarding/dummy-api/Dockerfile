# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /uvx /bin/

WORKDIR /app

COPY dummy-api/pyproject.toml ./pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv uv sync --no-dev --no-install-project

COPY shared ./shared
COPY dummy-api/app.py ./app.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

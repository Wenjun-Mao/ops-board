from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tenacity import retry, stop_after_attempt, wait_exponential

from ops_board_observe import OpsBoardSettings, bootstrap_observability, load_settings, observe

LOGGER = logging.getLogger("ops_board.dummy_api")
SERVICE_OVERRIDES = {
    "service_name": "dummy-api",
    "service_namespace": "ops-board.examples",
    "owner": "mk",
}


def _export_enabled() -> bool:
    return os.environ.get("OPS_BOARD_EXPORT", "true").strip().lower() not in {"0", "false", "no"}


def _load_api_settings() -> OpsBoardSettings:
    return load_settings(**SERVICE_OVERRIDES)


settings = _load_api_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global settings

    settings = bootstrap_observability(
        export=_export_enabled(),
        **SERVICE_OVERRIDES,
    )
    yield


app = FastAPI(title="Ops Board Dummy API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@retry(wait=wait_exponential(multiplier=0.1, min=0.1, max=1), stop=stop_after_attempt(3))
def simulated_external_dependency(item_id: str) -> dict[str, str]:
    return {"item_id": item_id, "source": "simulated-upstream"}


@observe("dummy-api.expensive-lookup")
def expensive_lookup(item_id: str) -> dict[str, int | str]:
    simulated_external_dependency(item_id)
    time.sleep(0.05)
    score = sum(ord(character) for character in item_id)
    LOGGER.info("dummy_api_lookup_completed", extra={"item_id": item_id, "score": score})
    return {"item_id": item_id, "score": score}


@app.get("/work/{item_id}")
@observe("dummy-api.work")
def run_work(item_id: str) -> dict[str, int | str]:
    result = expensive_lookup(item_id)
    return {
        "item_id": item_id,
        "status": "processed",
        "score": result["score"],
    }

from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.ops_observe import bootstrap_observability, observe

LOGGER = logging.getLogger("ops_board.dummy_api")


def _export_enabled() -> bool:
    return os.environ.get("OPS_BOARD_EXPORT", "true").strip().lower() not in {"0", "false", "no"}


settings = bootstrap_observability(
    service_name="dummy-api",
    service_namespace="ops-board.examples",
    owner="mk",
    export=_export_enabled(),
)

app = FastAPI(title="Ops Board Dummy API", version="0.1.0")


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

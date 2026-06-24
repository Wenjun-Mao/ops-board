from __future__ import annotations

import os
from collections.abc import Iterator

os.environ.setdefault("OPS_BOARD_EXPORT", "false")

from fastapi.testclient import TestClient
import ops_board_observe.instrumentation as instrumentation
import pytest
from ops_board_observe.instrumentation import _reset_for_tests

from app import app, expensive_lookup


@pytest.fixture(autouse=True)
def reset_observability() -> Iterator[None]:
    _reset_for_tests()
    yield
    _reset_for_tests()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("OPS_BOARD_EXPORT", "false")
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "dummy-api"


def test_work_endpoint_returns_demo_payload(client: TestClient):
    response = client.get("/work/demo")

    assert response.status_code == 200
    assert response.json()["item_id"] == "demo"
    assert response.json()["status"] == "processed"


def test_expensive_lookup_is_deterministic():
    assert expensive_lookup("abc") == {"item_id": "abc", "score": 294}


def test_client_context_runs_lifespan_bootstrap(client: TestClient):
    assert instrumentation._BOOTSTRAPPED is True

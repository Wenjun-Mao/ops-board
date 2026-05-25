from __future__ import annotations

import os

os.environ.setdefault("OPS_BOARD_EXPORT", "false")

from fastapi.testclient import TestClient

from app import app, expensive_lookup

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "dummy-api"


def test_work_endpoint_returns_demo_payload():
    response = client.get("/work/demo")

    assert response.status_code == 200
    assert response.json()["item_id"] == "demo"
    assert response.json()["status"] == "processed"


def test_expensive_lookup_is_deterministic():
    assert expensive_lookup("abc") == {"item_id": "abc", "score": 294}

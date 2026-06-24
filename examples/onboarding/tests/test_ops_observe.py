from __future__ import annotations

import pytest

from ops_board_observe import load_settings, observe


def test_load_settings_precedence(tmp_path, monkeypatch):
    config_file = tmp_path / "ops-board.yaml"
    config_file.write_text(
        """
service:
  name: config-service
  namespace: config-namespace
  environment: config-env
  owner: config-owner
runtime:
  host: config-host
ops_board:
  otlp_endpoint: http://config-collector:4318
  health_url: http://config-service:8000/health
""",
        encoding="utf-8",
    )

    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "service_name").write_text("secret-service", encoding="utf-8")

    monkeypatch.setenv("OPS_BOARD_SECRETS_DIR", str(secrets_dir))
    monkeypatch.setenv("OPS_BOARD_OWNER", "env-owner")
    monkeypatch.setenv("OPS_BOARD_ENVIRONMENT", "env")

    settings = load_settings(
        config_path=config_file,
        service_namespace="arg-namespace",
    )

    assert settings.service_name == "secret-service"
    assert settings.service_namespace == "arg-namespace"
    assert settings.environment == "env"
    assert settings.owner == "env-owner"
    assert settings.runtime_host == "config-host"
    assert settings.otlp_endpoint == "http://config-collector:4318"
    assert settings.health_url == "http://config-service:8000/health"


def test_observe_returns_wrapped_function_result():
    @observe("unit.success")
    def add(left: int, right: int) -> int:
        return left + right

    assert add(2, 3) == 5


def test_observe_records_and_reraises_exceptions():
    @observe("unit.failure")
    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        fail()

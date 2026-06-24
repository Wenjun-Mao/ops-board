from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest


OPS_BOARD_ENV_KEYS = [
    "OPS_BOARD_CONFIG_FILE",
    "OPS_BOARD_ENVIRONMENT",
    "OPS_BOARD_HEALTH_URL",
    "OPS_BOARD_OTLP_ENDPOINT",
    "OPS_BOARD_OWNER",
    "OPS_BOARD_RUNTIME_COUNTRY",
    "OPS_BOARD_RUNTIME_HOST",
    "OPS_BOARD_RUNTIME_PROVIDER",
    "OPS_BOARD_SECRETS_DIR",
    "OPS_BOARD_SERVICE_NAME",
    "OPS_BOARD_SERVICE_NAMESPACE",
    "OPS_BOARD_TAILSCALE_HOST",
    "OPS_BOARD_VERSION",
]


def _clear_ops_board_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in OPS_BOARD_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _settings_api() -> tuple[type[Any], Any]:
    try:
        from ops_board_observe import OpsBoardSettings, load_settings
    except ImportError as exc:
        pytest.fail(f"settings API is not implemented: {exc}")

    return OpsBoardSettings, load_settings


def test_load_settings_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_ops_board_env(monkeypatch)
    _, load_settings = _settings_api()
    config_path = tmp_path / "ops-board.yaml"
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()

    config_path.write_text(
        textwrap.dedent(
            """
            service:
              name: config-service
              namespace: config-namespace
              environment: config
              owner: config-owner
              version: 9.9.9
            runtime:
              host: config-host
              tailscale_host: config-tailnet-host
              provider: local
              country: CA
            ops_board:
              otlp_endpoint: http://config-collector:4318
              health_url: http://config-service:8000/health
            """
        ),
        encoding="utf-8",
    )
    (secrets_dir / "service_name").write_text("secret-service\n", encoding="utf-8")
    monkeypatch.setenv("OPS_BOARD_OWNER", "env-owner")
    monkeypatch.setenv("OPS_BOARD_ENVIRONMENT", "env")
    monkeypatch.setenv("OPS_BOARD_SECRETS_DIR", str(secrets_dir))

    settings = load_settings(
        config_path=config_path,
        service_namespace="arg-namespace",
    )

    assert settings.service_name == "secret-service"
    assert settings.service_namespace == "arg-namespace"
    assert settings.environment == "env"
    assert settings.owner == "env-owner"
    assert settings.version == "9.9.9"
    assert settings.runtime_host == "config-host"
    assert settings.tailscale_host == "config-tailnet-host"
    assert settings.runtime_provider == "local"
    assert settings.runtime_country == "CA"
    assert settings.otlp_endpoint == "http://config-collector:4318"
    assert settings.health_url == "http://config-service:8000/health"


def test_settings_defaults_are_safe_for_local_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_ops_board_env(monkeypatch)
    OpsBoardSettings, _ = _settings_api()

    settings = OpsBoardSettings()

    assert settings.service_name == "unknown-service"
    assert settings.service_namespace == "default"
    assert settings.environment == "local"
    assert settings.owner == "unknown"
    assert settings.otlp_endpoint == "http://localhost:4318"


def test_invalid_config_file_shape_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_ops_board_env(monkeypatch)
    _, load_settings = _settings_api()
    config_path = tmp_path / "ops-board.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Config file must contain a YAML mapping"):
        load_settings(config_path=config_path)

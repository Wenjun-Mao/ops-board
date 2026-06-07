from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bootstrap import (  # noqa: E402
    BootstrapConfig,
    MonitorDefinition,
    Settings,
    build_monitor_payload,
    load_bootstrap_config,
    missing_monitors,
    _require_ok,
)


def test_monitor_payload_matches_uptime_kuma_defaults() -> None:
    definition = MonitorDefinition(
        name="Homepage",
        type="http",
        url="http://host.docker.internal:3000",
        accepted_statuscodes=["200-299"],
    )

    payload = build_monitor_payload(definition)

    assert payload["type"] == "http"
    assert payload["name"] == "Homepage"
    assert payload["method"] == "GET"
    assert payload["interval"] == 60
    assert payload["retryInterval"] == 60
    assert payload["accepted_statuscodes"] == ["200-299"]
    assert payload["notificationIDList"] == {}
    assert payload["kafkaProducerBrokers"] == []
    assert payload["kafkaProducerSaslOptions"] == {"mechanism": "None"}
    assert payload["rabbitmqNodes"] == []
    assert payload["conditions"] == []


def test_optional_monitor_payload_is_inactive_by_default() -> None:
    definition = MonitorDefinition(
        name="Dummy API Health",
        type="http",
        url="http://host.docker.internal:18080/health",
        optional=True,
    )

    payload = build_monitor_payload(definition)

    assert payload["active"] is False


def test_missing_monitor_names_are_idempotent() -> None:
    existing = {"Homepage": {"id": 1, "name": "Homepage"}}
    configured = [
        MonitorDefinition(name="Homepage", type="http", url="http://host.docker.internal:3000"),
        MonitorDefinition(name="Plane", type="http", url="http://host.docker.internal:8082"),
    ]

    assert [monitor.name for monitor in missing_monitors(configured, existing)] == ["Plane"]


def test_password_file_takes_priority(tmp_path: Path) -> None:
    password_file = tmp_path / "uptime_kuma_admin_password"
    password_file.write_text("from-file", encoding="ascii")

    settings = Settings(
        repo_root=tmp_path,
        admin_password="from-env",
        admin_password_file=password_file,
    )

    assert settings.read_admin_password().get_secret_value() == "from-file"


def test_password_can_come_from_env_value(tmp_path: Path) -> None:
    settings = Settings(
        repo_root=tmp_path,
        admin_password="from-env",
        admin_password_file=tmp_path / "missing",
    )

    assert settings.read_admin_password().get_secret_value() == "from-env"


def test_missing_password_raises_clear_error(tmp_path: Path) -> None:
    settings = Settings(repo_root=tmp_path, admin_password_file=tmp_path / "missing")

    with pytest.raises(ValueError, match="Uptime Kuma admin password"):
        settings.read_admin_password()


def test_load_bootstrap_config(tmp_path: Path) -> None:
    config_path = tmp_path / "monitors.yaml"
    config_path.write_text(
        """
status_page:
  slug: ops-board
  title: Ops Board
monitors:
  - name: Homepage
    type: http
    url: http://host.docker.internal:3000
""",
        encoding="utf-8",
    )

    config = load_bootstrap_config(config_path)

    assert isinstance(config, BootstrapConfig)
    assert config.status_page.slug == "ops-board"
    assert config.monitors[0].name == "Homepage"


def test_login_auth_failure_mentions_existing_admin_mismatch() -> None:
    with pytest.raises(RuntimeError, match="already initialized"):
        _require_ok({"ok": False, "msg": "authIncorrectCreds"}, "login")

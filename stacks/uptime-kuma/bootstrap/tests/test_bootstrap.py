from pathlib import Path
import sys
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bootstrap as bootstrap_module  # noqa: E402
from bootstrap import (  # noqa: E402
    BootstrapConfig,
    MonitorDefinition,
    ProjectMonitorDefinition,
    Settings,
    build_monitor_payload,
    build_project_monitor_payload,
    build_project_monitor_update_payload,
    load_bootstrap_config,
    missing_monitors,
    project_monitor_description,
    reconcile_project_monitors,
    _require_ok,
)


class FakeKumaClient:
    def __init__(self, monitor_list: dict[str, dict[str, Any]] | None = None) -> None:
        self.monitor_list = monitor_list or {}
        self.added: list[dict[str, Any]] = []
        self.edited: list[dict[str, Any]] = []
        self.status_page_monitor_ids: list[int] | None = None

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def need_setup(self) -> bool:
        return False

    def setup(self, username: str, password: Any) -> None:
        raise AssertionError("setup should not be called")

    def login(self, username: str, password: Any) -> None:
        pass

    def get_monitor_list(self) -> dict[str, dict[str, Any]]:
        return self.monitor_list

    def add_monitor(self, payload: dict[str, Any]) -> int:
        monitor_id = str(len(self.monitor_list) + 1)
        monitor = dict(payload)
        monitor["id"] = int(monitor_id)
        self.monitor_list[monitor_id] = monitor
        self.added.append(monitor)
        return int(monitor_id)

    def edit_monitor(self, payload: dict[str, Any]) -> None:
        self.monitor_list[str(payload["id"])] = dict(payload)
        self.edited.append(dict(payload))

    def ensure_status_page(self, status_page: Any, monitor_ids: list[int]) -> None:
        self.status_page_monitor_ids = monitor_ids


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


def test_project_monitor_payload_uses_registry_defaults() -> None:
    definition = ProjectMonitorDefinition(
        id="spark-h3-gateway",
        name="Spark H3 Gateway",
        url="http://100.64.35.71:8090/health",
    )

    payload = build_project_monitor_payload(definition)

    assert payload["type"] == "http"
    assert payload["active"] is True
    assert payload["interval"] == 60
    assert payload["retryInterval"] == 60
    assert payload["maxretries"] == 0
    assert payload["ignoreTls"] is False
    assert payload["description"] == (
        "Ops Board registry ID: spark-h3-gateway\n"
        "Managed by the Ops Board project-monitor registry."
    )


def test_project_monitor_rejects_non_http_url() -> None:
    with pytest.raises(ValueError, match="http:// or https://"):
        ProjectMonitorDefinition(
            id="spark-h3-gateway",
            name="Spark H3 Gateway",
            url="spark-h3-gateway:8090/health",
        )


def test_bootstrap_config_rejects_duplicate_project_monitor_ids() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        BootstrapConfig(
            status_page={"slug": "ops-board", "title": "Ops Board"},
            monitors=[],
            project_monitors=[
                {
                    "id": "duplicate",
                    "name": "One",
                    "url": "http://one.example/health",
                },
                {
                    "id": "duplicate",
                    "name": "Two",
                    "url": "https://two.example/health",
                },
            ],
        )


def test_reconcile_project_monitors_creates_a_new_registry_monitor() -> None:
    client = FakeKumaClient()
    definition = ProjectMonitorDefinition(
        id="spark-h3-gateway",
        name="Spark H3 Gateway",
        url="http://100.64.35.71:8090/health",
    )

    reconcile_project_monitors(client, [definition])

    assert len(client.added) == 1
    assert client.added[0]["name"] == "Spark H3 Gateway"
    assert client.added[0]["description"] == project_monitor_description(definition)


def test_reconcile_project_monitors_updates_owned_monitor_and_preserves_notifications() -> None:
    definition = ProjectMonitorDefinition(
        id="spark-h3-gateway",
        name="Spark H3 Gateway",
        url="http://100.64.35.71:8090/health",
    )
    existing = build_project_monitor_payload(definition)
    existing.update(
        {
            "id": 42,
            "name": "Old Spark Gateway",
            "url": "http://100.64.35.71:8090/old-health",
            "notificationIDList": {"7": True},
        }
    )
    client = FakeKumaClient({"42": existing})

    reconcile_project_monitors(client, [definition])

    assert client.added == []
    assert len(client.edited) == 1
    assert client.edited[0]["id"] == 42
    assert client.edited[0]["name"] == "Spark H3 Gateway"
    assert client.edited[0]["url"] == "http://100.64.35.71:8090/health"
    assert client.edited[0]["notificationIDList"] == {"7": True}


def test_project_monitor_update_is_idempotent() -> None:
    definition = ProjectMonitorDefinition(
        id="spark-h3-gateway",
        name="Spark H3 Gateway",
        url="http://100.64.35.71:8090/health",
    )
    existing = build_project_monitor_payload(definition)
    existing["id"] = 42
    client = FakeKumaClient({"42": existing})

    reconcile_project_monitors(client, [definition])

    assert client.added == []
    assert client.edited == []


def test_registry_never_claims_a_same_named_manual_monitor() -> None:
    definition = ProjectMonitorDefinition(
        id="spark-h3-gateway",
        name="Spark H3 Gateway",
        url="http://100.64.35.71:8090/health",
    )
    client = FakeKumaClient({"9": {"id": 9, "name": definition.name}})

    with pytest.raises(RuntimeError, match="not owned by the Ops Board registry"):
        reconcile_project_monitors(client, [definition])

    assert client.added == []
    assert client.edited == []


def test_project_registry_removal_does_not_delete_existing_monitor() -> None:
    definition = ProjectMonitorDefinition(
        id="spark-h3-gateway",
        name="Spark H3 Gateway",
        url="http://100.64.35.71:8090/health",
    )
    existing = build_project_monitor_payload(definition)
    existing["id"] = 42
    client = FakeKumaClient({"42": existing})

    reconcile_project_monitors(client, [])

    assert client.monitor_list == {"42": existing}
    assert client.added == []
    assert client.edited == []


def test_project_monitor_update_payload_keeps_unmanaged_monitor_fields() -> None:
    definition = ProjectMonitorDefinition(
        id="spark-h3-gateway",
        name="Spark H3 Gateway",
        url="http://100.64.35.71:8090/health",
    )
    existing = build_project_monitor_payload(definition)
    existing.update({"id": 42, "headers": "X-Debug: enabled", "notificationIDList": {"7": True}})

    payload = build_project_monitor_update_payload(existing, definition)

    assert payload["headers"] == "X-Debug: enabled"
    assert payload["notificationIDList"] == {"7": True}


def test_bootstrap_keeps_project_monitors_off_the_core_status_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "monitors.yaml"
    config_path.write_text(
        """
status_page:
  slug: ops-board
  title: Ops Board
monitors:
  - name: Homepage
    url: http://host.docker.internal:3000
project_monitors:
  - id: spark-h3-gateway
    name: Spark H3 Gateway
    url: http://100.64.35.71:8090/health
""",
        encoding="utf-8",
    )
    clients: list[FakeKumaClient] = []

    def create_client(*_: Any) -> FakeKumaClient:
        client = FakeKumaClient()
        clients.append(client)
        return client

    monkeypatch.setattr(bootstrap_module, "KumaClient", create_client)
    settings = Settings(
        repo_root=tmp_path,
        bootstrap_config=config_path,
        admin_password="test-password",
    )

    bootstrap_module.bootstrap(settings)

    assert len(clients) == 1
    assert clients[0].status_page_monitor_ids == [1]


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

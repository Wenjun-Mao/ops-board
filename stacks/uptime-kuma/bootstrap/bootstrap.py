from __future__ import annotations

import argparse
import sys
from pathlib import Path
from threading import Event
from typing import Any

import socketio
import yaml
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
)


DOCKER_SECRET_PASSWORD_PATH = Path("/run/secrets/uptime_kuma_admin_password")


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "compose.yaml").exists() and (candidate / ".env.example").exists():
            return candidate

    return Path.cwd()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UPTIME_KUMA_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    repo_root: Path = Field(default_factory=find_repo_root)
    public_url: str = "http://localhost:3001"
    admin_username: str = "ops-board-demo"
    admin_password: SecretStr | None = None
    admin_password_file: Path = Path("secrets/uptime_kuma_admin_password")
    bootstrap_config: Path = Path("stacks/uptime-kuma/bootstrap/monitors.yaml")
    socket_timeout_seconds: float = 20

    @classmethod
    def load(cls, repo_root: Path | None = None) -> Settings:
        root = repo_root or find_repo_root()
        env_file = root / ".env"
        return cls(repo_root=root, _env_file=env_file if env_file.exists() else None)

    def resolve_repo_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return self.repo_root / path

    def resolved_config_path(self) -> Path:
        return self.resolve_repo_path(self.bootstrap_config)

    def read_admin_password(self) -> SecretStr:
        docker_secret = self._read_secret_file(DOCKER_SECRET_PASSWORD_PATH)
        if docker_secret is not None:
            return docker_secret

        configured_file = self.resolve_repo_path(self.admin_password_file)
        file_secret = self._read_secret_file(configured_file)
        if file_secret is not None:
            return file_secret

        if self.admin_password is not None:
            password = self.admin_password.get_secret_value().strip()
            if password:
                return SecretStr(password)

        raise ValueError(
            "Uptime Kuma admin password is required. Set "
            "UPTIME_KUMA_ADMIN_PASSWORD_FILE or UPTIME_KUMA_ADMIN_PASSWORD."
        )

    @staticmethod
    def _read_secret_file(path: Path) -> SecretStr | None:
        if not path.exists():
            return None

        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise ValueError(f"Uptime Kuma admin password file is empty: {path}")

        return SecretStr(value)


class StatusPageConfig(BaseModel):
    slug: str
    title: str
    description: str = ""


class MonitorDefinition(BaseModel):
    name: str
    type: str = "http"
    url: str
    accepted_statuscodes: list[str] = Field(default_factory=lambda: ["200-299"])
    optional: bool = False


class BootstrapConfig(BaseModel):
    status_page: StatusPageConfig
    monitors: list[MonitorDefinition]


def load_bootstrap_config(path: Path) -> BootstrapConfig:
    with path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file)

    return BootstrapConfig.model_validate(raw_config)


def build_monitor_payload(definition: MonitorDefinition) -> dict[str, Any]:
    return {
        "type": definition.type,
        "name": definition.name,
        "parent": None,
        "url": definition.url,
        "method": "GET",
        "protocol": None,
        "location": "world",
        "ipFamily": None,
        "interval": 60,
        "retryInterval": 60,
        "resendInterval": 0,
        "maxretries": 0,
        "retryOnlyOnStatusCodeFailure": False,
        "notificationIDList": {},
        "ignoreTls": False,
        "upsideDown": False,
        "expiryNotification": False,
        "domainExpiryNotification": True,
        "maxredirects": 10,
        "accepted_statuscodes": definition.accepted_statuscodes,
        "saveResponse": False,
        "saveErrorResponse": True,
        "responseMaxLength": 1024,
        "dns_resolve_type": "A",
        "dns_resolve_server": "",
        "docker_container": "",
        "docker_host": None,
        "proxyId": None,
        "basic_auth_user": "",
        "basic_auth_pass": "",
        "authMethod": None,
        "httpBodyEncoding": "json",
        "body": "",
        "headers": "",
        "kafkaProducerBrokers": [],
        "kafkaProducerSaslOptions": {"mechanism": "None"},
        "cacheBust": False,
        "kafkaProducerSsl": False,
        "kafkaProducerAllowAutoTopicCreation": False,
        "gamedigGivenPortOnly": True,
        "remote_browser": None,
        "screenshot_delay": 0,
        "rabbitmqNodes": [],
        "rabbitmqUsername": "",
        "rabbitmqPassword": "",
        "conditions": [],
        "system_service_name": "",
        "active": not definition.optional,
    }


def missing_monitors(
    configured: list[MonitorDefinition],
    existing_by_name: dict[str, dict[str, Any]],
) -> list[MonitorDefinition]:
    return [monitor for monitor in configured if monitor.name not in existing_by_name]


class KumaClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.monitor_list: dict[str, dict[str, Any]] = {}
        self.monitor_list_received = Event()
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=1,
            reconnection_delay_max=5,
            logger=False,
            engineio_logger=False,
        )
        self.sio.on("monitorList", self._handle_monitor_list)

    def _handle_monitor_list(self, monitor_list: dict[str, dict[str, Any]]) -> None:
        self.monitor_list = monitor_list
        self.monitor_list_received.set()

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_delay(60),
        reraise=True,
    )
    def connect(self) -> None:
        if not self.sio.connected:
            self.sio.connect(self.base_url)

    def disconnect(self) -> None:
        if self.sio.connected:
            self.sio.disconnect()

    @retry(
        retry=retry_if_exception_type(socketio.exceptions.TimeoutError),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def call(self, event: str, *args: Any) -> Any:
        if len(args) == 0:
            data = None
        elif len(args) == 1:
            data = args[0]
        else:
            data = args

        return self.sio.call(event, data=data, timeout=self.timeout_seconds)

    def need_setup(self) -> bool:
        return bool(self.call("needSetup"))

    def setup(self, username: str, password: SecretStr) -> None:
        response = self.call("setup", username, password.get_secret_value())
        _require_ok(response, "setup")

    def login(self, username: str, password: SecretStr) -> None:
        response = self.call(
            "login",
            {
                "username": username,
                "password": password.get_secret_value(),
            },
        )
        _require_ok(response, "login")

    def get_monitor_list(self) -> dict[str, dict[str, Any]]:
        self.monitor_list = {}
        self.monitor_list_received.clear()
        response = self.call("getMonitorList")
        _require_ok(response, "getMonitorList")

        if not self.monitor_list_received.wait(self.timeout_seconds):
            raise TimeoutError("Timed out waiting for Uptime Kuma monitorList event.")

        return self.monitor_list

    def add_monitor(self, payload: dict[str, Any]) -> int:
        response = self.call("add", payload)
        _require_ok(response, "add")
        monitor_id = response.get("monitorID")
        if monitor_id is None:
            raise RuntimeError("Uptime Kuma add response did not include monitorID.")
        return int(monitor_id)

    def ensure_status_page(self, status_page: StatusPageConfig, monitor_ids: list[int]) -> None:
        page_response = self.call("getStatusPage", status_page.slug)
        if not _is_ok(page_response):
            add_response = self.call("addStatusPage", status_page.title, status_page.slug)
            _require_ok(add_response, "addStatusPage")
            page_response = self.call("getStatusPage", status_page.slug)

        _require_ok(page_response, "getStatusPage")
        existing_config = page_response.get("config") or {}
        page_config = _build_status_page_config(status_page, existing_config)
        public_group_list = [
            {
                "name": status_page.title,
                "monitorList": [{"id": monitor_id} for monitor_id in monitor_ids],
            }
        ]

        response = self.call(
            "saveStatusPage",
            status_page.slug,
            page_config,
            page_config["logo"],
            public_group_list,
        )
        _require_ok(response, "saveStatusPage")


def bootstrap(settings: Settings, skip_optional: bool = False) -> None:
    config = load_bootstrap_config(settings.resolved_config_path())
    password = settings.read_admin_password()
    monitors_to_consider = [
        monitor for monitor in config.monitors if not (skip_optional and monitor.optional)
    ]
    client = KumaClient(settings.public_url, settings.socket_timeout_seconds)

    try:
        client.connect()
        if client.need_setup():
            client.setup(settings.admin_username, password)
            print(f"Created Uptime Kuma admin user: {settings.admin_username}")
        else:
            print("Uptime Kuma admin setup already complete.")

        client.login(settings.admin_username, password)
        existing_by_name = _monitor_list_by_name(client.get_monitor_list())
        missing = missing_monitors(monitors_to_consider, existing_by_name)

        for monitor in missing:
            client.add_monitor(build_monitor_payload(monitor))
            print(f"Created monitor: {monitor.name}")

        if not missing:
            print("All configured monitors already exist.")

        refreshed_by_name = _monitor_list_by_name(client.get_monitor_list())
        baseline_monitor_ids = [
            int(refreshed_by_name[monitor.name]["id"])
            for monitor in monitors_to_consider
            if monitor.name in refreshed_by_name
        ]
        client.ensure_status_page(config.status_page, baseline_monitor_ids)
        print(f"Status page ready: /status/{config.status_page.slug}")
    finally:
        client.disconnect()


def _monitor_list_by_name(
    monitor_list: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for monitor_id, monitor in monitor_list.items():
        name = monitor.get("name")
        if not name:
            continue
        monitor_with_id = dict(monitor)
        monitor_with_id.setdefault("id", monitor_id)
        by_name[str(name)] = monitor_with_id
    return by_name


def _build_status_page_config(
    status_page: StatusPageConfig,
    existing_config: dict[str, Any],
) -> dict[str, Any]:
    description = status_page.description or existing_config.get("description") or ""

    return {
        "slug": status_page.slug,
        "title": status_page.title,
        "description": description,
        "logo": existing_config.get("icon") or existing_config.get("logo") or "",
        "autoRefreshInterval": existing_config.get("autoRefreshInterval") or 300,
        "theme": existing_config.get("theme") or "auto",
        "showTags": existing_config.get("showTags") or False,
        "footerText": existing_config.get("footerText") or "",
        "customCSS": existing_config.get("customCSS") or "",
        "showPoweredBy": existing_config.get("showPoweredBy") or False,
        "rssTitle": existing_config.get("rssTitle") or "",
        "showOnlyLastHeartbeat": existing_config.get("showOnlyLastHeartbeat") or False,
        "showCertificateExpiry": existing_config.get("showCertificateExpiry") or False,
        "analyticsId": existing_config.get("analyticsId") or "",
        "analyticsScriptUrl": existing_config.get("analyticsScriptUrl") or "",
        "analyticsType": existing_config.get("analyticsType"),
        "domainNameList": existing_config.get("domainNameList") or [],
    }


def _is_ok(response: Any) -> bool:
    return isinstance(response, dict) and response.get("ok") is True


def _require_ok(response: Any, action: str) -> None:
    if _is_ok(response):
        return

    message = "unknown error"
    if isinstance(response, dict):
        message = str(response.get("msg") or response.get("error") or message)

    if action == "login" and message == "authIncorrectCreds":
        message = (
            "authIncorrectCreds. Uptime Kuma is already initialized with a "
            "different admin credential. Update UPTIME_KUMA_ADMIN_USERNAME and "
            "UPTIME_KUMA_ADMIN_PASSWORD_FILE to match the existing local account, "
            "or reset the Uptime Kuma volume before first-run bootstrap."
        )

    raise RuntimeError(f"Uptime Kuma {action} failed: {message}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap the local Ops Board Uptime Kuma instance."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to monitor/status-page YAML. Defaults to UPTIME_KUMA_BOOTSTRAP_CONFIG.",
    )
    parser.add_argument(
        "--skip-optional",
        action="store_true",
        help="Skip monitors marked optional in the YAML config.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.load()
    if args.config is not None:
        settings.bootstrap_config = args.config

    try:
        bootstrap(settings, skip_optional=args.skip_optional)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

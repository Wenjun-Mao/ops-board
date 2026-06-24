from __future__ import annotations

import os
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential


class OpsBoardSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPS_BOARD_", extra="ignore")

    service_name: str = "unknown-service"
    service_namespace: str = "default"
    environment: str = "local"
    owner: str = "unknown"
    version: str = "0.1.0"
    runtime_host: str = Field(default_factory=socket.gethostname)
    tailscale_host: str | None = None
    runtime_provider: str | None = None
    runtime_country: str | None = None
    otlp_endpoint: str = "http://localhost:4318"
    health_url: str | None = None
    secrets_dir: str = "/run/secrets"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, max=1),
    reraise=True,
)
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_settings(config_path: str | Path | None = None, **overrides: Any) -> OpsBoardSettings:
    normalized_overrides = _normalize_settings_values(overrides)
    config_values = _load_config_values(_resolve_config_path(config_path))
    env_values = _environment_values()
    secrets_dir = _resolve_secrets_dir(config_values, env_values, normalized_overrides)
    secret_values = _secret_values(secrets_dir)

    values: dict[str, Any] = {}
    values.update(config_values)
    values.update(env_values)
    values.update(secret_values)
    values.update(normalized_overrides)
    return OpsBoardSettings(**values)


def _resolve_config_path(config_path: str | Path | None) -> Path | None:
    if config_path is not None:
        return Path(config_path)

    env_config_path = os.environ.get("OPS_BOARD_CONFIG_FILE")
    if env_config_path:
        return Path(env_config_path)

    default_path = Path("ops-board.yaml")
    if default_path.exists():
        return default_path
    return None


def _load_config_values(config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        return {}

    loaded = yaml.safe_load(_read_text(config_path))
    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise ValueError("Config file must contain a YAML mapping")

    service = _mapping_section(loaded, "service")
    runtime = _mapping_section(loaded, "runtime")
    ops_board = _mapping_section(loaded, "ops_board")
    return _without_none(
        {
            "service_name": service.get("name"),
            "service_namespace": service.get("namespace"),
            "environment": service.get("environment"),
            "owner": service.get("owner"),
            "version": service.get("version"),
            "runtime_host": runtime.get("host"),
            "tailscale_host": runtime.get("tailscale_host"),
            "runtime_provider": runtime.get("provider"),
            "runtime_country": runtime.get("country"),
            "otlp_endpoint": ops_board.get("otlp_endpoint"),
            "health_url": ops_board.get("health_url"),
        }
    )


def _mapping_section(config: Mapping[Any, Any], section_name: str) -> Mapping[Any, Any]:
    section = config.get(section_name, {})
    if section is None:
        return {}
    if not isinstance(section, Mapping):
        raise ValueError(f"Config section '{section_name}' must contain a YAML mapping")
    return section


def _environment_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for field_name in OpsBoardSettings.model_fields:
        env_name = f"OPS_BOARD_{field_name.upper()}"
        if env_name in os.environ:
            values[field_name] = os.environ[env_name]
    return values


def _resolve_secrets_dir(
    config_values: Mapping[str, Any],
    env_values: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> Path:
    secrets_dir = (
        overrides.get("secrets_dir")
        or env_values.get("secrets_dir")
        or config_values.get("secrets_dir")
        or OpsBoardSettings.model_fields["secrets_dir"].default
    )
    return Path(str(secrets_dir))


def _secret_values(secrets_dir: Path) -> dict[str, str]:
    if not secrets_dir.exists():
        return {}

    values: dict[str, str] = {}
    for field_name in OpsBoardSettings.model_fields:
        secret_path = secrets_dir / field_name
        if secret_path.is_file():
            values[field_name] = _read_text(secret_path).strip()
    return values


def _without_none(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _normalize_settings_values(values: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(values)
    secrets_dir = normalized.get("secrets_dir")
    if isinstance(secrets_dir, os.PathLike):
        normalized["secrets_dir"] = str(secrets_dir)
    return normalized

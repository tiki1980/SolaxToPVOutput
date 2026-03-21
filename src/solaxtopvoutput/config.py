"""Configuration loading and validation."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

APP_NAME = "SolaxToPVOutput"
CONFIG_FILE_NAME = "config.yml"
ENV_CONFIG_PATH = "SOLAXTOPVOUTPUT_CONFIG"
ENV_LOG_LEVEL = "SOLAXTOPVOUTPUT_LOG_LEVEL"
ENV_POLL_INTERVAL = "SOLAXTOPVOUTPUT_POLL_INTERVAL_SECONDS"
ENV_LOG_FILE = "SOLAXTOPVOUTPUT_LOG_FILE"
ENV_SOLAX_API_URL = "SOLAXCLOUD_API_URL"
ENV_SOLAX_TOKEN_ID = "SOLAXCLOUD_TOKEN_ID"
ENV_SOLAX_REGISTRATION_NR = "SOLAXCLOUD_REGISTRATION_NR"
ENV_PVOUTPUT_SYSTEM_ID = "PVOUTPUT_SYSTEM_ID"
ENV_PVOUTPUT_API_KEY = "PVOUTPUT_API_KEY"


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the application."""

    log_level: str = "WARNING"
    poll_interval_seconds: int = 300
    log_file: str = "solaxtopvoutput.log"


@dataclass(frozen=True)
class SolaxCloudConfig:
    """SolaxCloud API settings."""

    api_url: str
    token_id: str
    registration_nr: str


@dataclass(frozen=True)
class PVOutputConfig:
    """PVOutput API settings."""

    system_id: int
    api_key: str


@dataclass(frozen=True)
class Config:
    """Top-level application configuration."""

    app: AppConfig
    solax_cloud: SolaxCloudConfig
    pvoutput: PVOutputConfig
    config_path: Path

    @property
    def log_path(self) -> Path:
        """Return the resolved application log path."""

        log_file = Path(self.app.log_file)
        if log_file.is_absolute():
            return log_file
        return self.config_path.parent / log_file


def config_search_paths() -> list[Path]:
    """Return config locations in lookup order."""

    env_path = os.environ.get(ENV_CONFIG_PATH)
    if env_path:
        return [Path(env_path).expanduser()]

    return [user_config_path(), Path.cwd() / CONFIG_FILE_NAME]


def default_config_path() -> Path:
    """Return the preferred default config location."""

    for path in config_search_paths():
        if path.exists():
            return path
    return config_search_paths()[0]


def user_config_path() -> Path:
    """Return the per-user config path for this application."""

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME / CONFIG_FILE_NAME

    xdg_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_home:
        return Path(xdg_home) / "solaxtopvoutput" / CONFIG_FILE_NAME

    return Path.home() / ".config" / "solaxtopvoutput" / CONFIG_FILE_NAME


def load_config(path: Path) -> Config:
    """Load and validate configuration from YAML and environment."""

    raw_config = _load_yaml_config(path)
    app_section = _require_mapping(raw_config, "SolaxToPVOutput")
    solax_section = _require_mapping(raw_config, "SolaxCloud")
    pvoutput_section = _require_mapping(raw_config, "PVOutput")

    app_data = _merge_app_config(app_section)
    solax_data = _merge_solax_config(solax_section)
    pvoutput_data = _merge_pvoutput_config(pvoutput_section)

    app = AppConfig(
        log_level=str(app_data.get("logLevel", "WARNING")).upper(),
        poll_interval_seconds=int(app_data.get("pollIntervalSeconds", 300)),
        log_file=str(app_data.get("logFile", "solaxtopvoutput.log")),
    )
    if app.poll_interval_seconds <= 0:
        raise ValueError(
            "SolaxToPVOutput.pollIntervalSeconds must be greater than zero"
        )

    _validate_log_level(app.log_level)

    return Config(
        app=app,
        solax_cloud=SolaxCloudConfig(
            api_url=str(_require_value(solax_data, "apiUrl")),
            token_id=str(_require_value(solax_data, "tokenId")),
            registration_nr=str(_require_value(solax_data, "registrationNr")),
        ),
        pvoutput=PVOutputConfig(
            system_id=int(_require_value(pvoutput_data, "systemid")),
            api_key=str(_require_value(pvoutput_data, "apikey")),
        ),
        config_path=path,
    )


def _load_yaml_config(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw_config = yaml.safe_load(handle) or {}
    except OSError as exc:
        raise ValueError(f"Unable to read config file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in config file: {path}") from exc

    if not isinstance(raw_config, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return raw_config


def _merge_app_config(section: Mapping[str, object]) -> dict[str, object]:
    merged = dict(section)
    _apply_env_override(merged, "logLevel", ENV_LOG_LEVEL)
    _apply_env_override(merged, "pollIntervalSeconds", ENV_POLL_INTERVAL)
    _apply_env_override(merged, "logFile", ENV_LOG_FILE)
    return merged


def _merge_solax_config(section: Mapping[str, object]) -> dict[str, object]:
    merged = dict(section)
    _apply_env_override(merged, "apiUrl", ENV_SOLAX_API_URL)
    _apply_env_override(merged, "tokenId", ENV_SOLAX_TOKEN_ID)
    _apply_env_override(merged, "registrationNr", ENV_SOLAX_REGISTRATION_NR)
    return merged


def _merge_pvoutput_config(
    section: Mapping[str, object],
) -> dict[str, object]:
    merged = dict(section)
    _apply_env_override(merged, "systemid", ENV_PVOUTPUT_SYSTEM_ID)
    _apply_env_override(merged, "apikey", ENV_PVOUTPUT_API_KEY)
    return merged


def _apply_env_override(
    section: dict[str, object],
    key: str,
    env_name: str,
) -> None:
    value = os.environ.get(env_name)
    if value not in (None, ""):
        section[key] = value


def _require_mapping(raw_config: dict, section: str) -> dict:
    value = raw_config.get(section)
    if not isinstance(value, dict):
        raise ValueError(f"Missing or invalid config section: {section}")
    return value


def _require_value(section: Mapping[str, object], key: str) -> object:
    value = section.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing config value: {key}")
    return value


def _validate_log_level(log_level: str) -> None:
    if not isinstance(getattr(logging, log_level, None), int):
        raise ValueError(f"Invalid log level: {log_level}")

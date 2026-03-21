"""Configuration loading and validation."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
VALID_START_EVENTS = {"dawn", "sunrise"}
VALID_END_EVENTS = {"sunset", "dusk"}


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
class SunWindowConfig:
    """Optional sun-based execution window configuration."""

    enabled: bool = False
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    start_event: str = "sunrise"
    end_event: str = "sunset"


@dataclass(frozen=True)
class Config:
    """Top-level application configuration."""

    app: AppConfig
    solax_cloud: SolaxCloudConfig
    pvoutput: PVOutputConfig
    sun_window: SunWindowConfig
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
    sun_window_section = _optional_mapping(raw_config, "SunWindow")

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
    sun_window = _build_sun_window_config(sun_window_section)

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
        sun_window=sun_window,
        config_path=path,
    )


def _build_sun_window_config(section: Mapping[str, object]) -> SunWindowConfig:
    enabled = _parse_bool(section.get("enabled", False))
    start_event = str(section.get("startEvent", "sunrise")).lower()
    end_event = str(section.get("endEvent", "sunset")).lower()

    if start_event not in VALID_START_EVENTS:
        valid_start_events = sorted(VALID_START_EVENTS)
        raise ValueError(
            "SunWindow.startEvent must be one of: " f"{valid_start_events}"
        )
    if end_event not in VALID_END_EVENTS:
        valid_end_events = sorted(VALID_END_EVENTS)
        raise ValueError(
            "SunWindow.endEvent must be one of: " f"{valid_end_events}"
        )

    latitude = _optional_float(section.get("latitude"))
    longitude = _optional_float(section.get("longitude"))
    timezone = _optional_string(section.get("timezone"))

    if enabled:
        if latitude is None or longitude is None or timezone is None:
            raise ValueError(
                "SunWindow requires latitude, longitude, and timezone "
                "when enabled"
            )
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"Invalid SunWindow.timezone value: {timezone}"
            ) from exc

    return SunWindowConfig(
        enabled=enabled,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        start_event=start_event,
        end_event=end_event,
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


def _optional_mapping(raw_config: dict, section: str) -> dict:
    value = raw_config.get(section, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Missing or invalid config section: {section}")
    return value


def _require_value(section: Mapping[str, object], key: str) -> object:
    value = section.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing config value: {key}")
    return value


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_string(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _validate_log_level(log_level: str) -> None:
    if not isinstance(getattr(logging, log_level, None), int):
        raise ValueError(f"Invalid log level: {log_level}")

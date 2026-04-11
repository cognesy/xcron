"""Typed loading for xcron logging configuration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from importlib.resources import files
import os
from typing import Any

import yaml


LOGGING_PACKAGE = "resources.logging"
LOGGING_CONFIG_NAME = "default.yaml"
LOG_LEVEL_ENV = "XCRON_LOG_LEVEL"
LOG_FORMAT_ENV = "XCRON_LOG_FORMAT"


@dataclass(frozen=True)
class LoggingEventsConfig:
    """Event families controlled by logging configuration."""

    actions: bool = True
    subprocesses: bool = True
    scheduler_wrappers: bool = True


@dataclass(frozen=True)
class LoggingFieldsConfig:
    """Field policy for structured log events."""

    include: tuple[str, ...] = ()
    redact: tuple[str, ...] = ("env", "token", "secret")


@dataclass(frozen=True)
class LoggingConfig:
    """Process logging configuration loaded from packaged resources."""

    version: int = 1
    logger: str = "xcron"
    destination: str = "stderr"
    format: str = "auto"
    level: str = "INFO"
    timestamp: str = "iso"
    events: LoggingEventsConfig = field(default_factory=LoggingEventsConfig)
    fields: LoggingFieldsConfig = field(default_factory=LoggingFieldsConfig)


DEFAULT_LOGGING_CONFIG = LoggingConfig()


def load_logging_config(*, apply_env: bool = True) -> LoggingConfig:
    """Load packaged logging config, optionally applying environment overrides."""

    resource = files(LOGGING_PACKAGE).joinpath(LOGGING_CONFIG_NAME)
    payload = yaml.safe_load(resource.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"logging config must be a mapping: {resource}")
    config = _parse_logging_config(payload)
    if apply_env:
        config = apply_logging_env_overrides(config)
        _validate_logging_config(config)
    return config


def apply_logging_env_overrides(config: LoggingConfig) -> LoggingConfig:
    """Apply supported environment overrides to one logging config."""

    level = os.environ.get(LOG_LEVEL_ENV)
    log_format = os.environ.get(LOG_FORMAT_ENV)
    if level is not None:
        config = replace(config, level=level.strip().upper())
    if log_format is not None:
        config = replace(config, format=log_format.strip().lower())
    return config


def _parse_logging_config(payload: dict[str, Any]) -> LoggingConfig:
    events = payload.get("events", {})
    fields = payload.get("fields", {})
    if not isinstance(events, dict):
        raise ValueError("logging config events must be a mapping")
    if not isinstance(fields, dict):
        raise ValueError("logging config fields must be a mapping")

    config = LoggingConfig(
        version=int(payload.get("version", DEFAULT_LOGGING_CONFIG.version)),
        logger=str(payload.get("logger", DEFAULT_LOGGING_CONFIG.logger)),
        destination=str(payload.get("destination", DEFAULT_LOGGING_CONFIG.destination)).lower(),
        format=str(payload.get("format", DEFAULT_LOGGING_CONFIG.format)).lower(),
        level=str(payload.get("level", DEFAULT_LOGGING_CONFIG.level)).upper(),
        timestamp=str(payload.get("timestamp", DEFAULT_LOGGING_CONFIG.timestamp)).lower(),
        events=LoggingEventsConfig(
            actions=bool(events.get("actions", DEFAULT_LOGGING_CONFIG.events.actions)),
            subprocesses=bool(events.get("subprocesses", DEFAULT_LOGGING_CONFIG.events.subprocesses)),
            scheduler_wrappers=bool(
                events.get("scheduler_wrappers", DEFAULT_LOGGING_CONFIG.events.scheduler_wrappers)
            ),
        ),
        fields=LoggingFieldsConfig(
            include=_string_tuple(fields.get("include", DEFAULT_LOGGING_CONFIG.fields.include)),
            redact=_string_tuple(fields.get("redact", DEFAULT_LOGGING_CONFIG.fields.redact)),
        ),
    )
    _validate_logging_config(config)
    return config


def _validate_logging_config(config: LoggingConfig) -> None:
    if config.version != 1:
        raise ValueError(f"unsupported logging config version: {config.version}")
    if config.destination != "stderr":
        raise ValueError(f"unsupported logging destination: {config.destination}")
    if config.format not in {"auto", "json", "console"}:
        raise ValueError(f"unsupported logging format: {config.format}")
    if config.timestamp != "iso":
        raise ValueError(f"unsupported logging timestamp: {config.timestamp}")


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise ValueError("logging config field lists must be lists of strings")
    return tuple(str(item) for item in value)

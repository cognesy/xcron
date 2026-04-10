"""Shared CLI helper functions for xcron shells."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from libs.services import CommandContract, ValidationMessage, parse_fields_csv, validate_requested_fields


def resolve_project_path(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return Path.cwd().resolve()


def env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser().resolve()


def env_string(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value else None


def env_flag(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value not in {"0", "false", "False", "no", "NO"}


def selected_contract_fields(contract: CommandContract, value: str | None) -> tuple[str, ...]:
    return validate_requested_fields(contract, parse_fields_csv(value))


def validation_details(messages: Sequence[ValidationMessage]) -> list[dict[str, str]]:
    return [{"field": message.path, "issue": message.message} for message in messages]

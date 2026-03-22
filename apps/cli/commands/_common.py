"""Common helpers for CLI command modules."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

from libs.domain import PlanChange, StatusEntry
from libs.services import ValidationMessage


def resolve_project_path(value: str | None) -> Path:
    """Resolve the project root without performing any domain validation."""
    if value:
        return Path(value).expanduser().resolve()
    return Path.cwd().resolve()


def env_path(name: str) -> Path | None:
    """Resolve an optional path override from the environment."""
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser().resolve()


def env_string(name: str) -> str | None:
    """Read an optional string override from the environment."""
    value = os.environ.get(name)
    return value if value else None


def env_flag(name: str, default: bool = True) -> bool:
    """Read a boolean flag from the environment."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value not in {"0", "false", "False", "no", "NO"}


def print_validation_messages(messages: Sequence[ValidationMessage]) -> None:
    """Print validation errors or warnings in a compact format."""
    for message in messages:
        print(f"{message.level.upper()} {message.path} {message.message}")


def print_plan_changes(changes: Iterable[PlanChange]) -> None:
    """Print plan changes in a readable one-line format."""
    for change in changes:
        print(f"{change.kind.value:<7} {change.qualified_id}  {change.reason}")


def print_status_entries(entries: Iterable[StatusEntry]) -> None:
    """Print operator-facing status entries in a readable one-line format."""
    for entry in entries:
        print(f"{entry.kind.value:<8} {entry.qualified_id}  {entry.reason}")

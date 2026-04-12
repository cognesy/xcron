"""Shared CLI helper functions for xcron shells."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from libs.services import ValidationMessage

VALID_OUTPUT_FORMATS = ("json", "toon", "tmux")


def resolve_project_path(value: str | None) -> Path:
    from libs.services.config_loader import resolve_project_root

    return resolve_project_root(value)


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
def selected_output_format(value: str | None) -> str:
    normalized = (value or "toon").strip().lower()
    if normalized not in VALID_OUTPUT_FORMATS:
        allowed = ", ".join(VALID_OUTPUT_FORMATS)
        raise ValueError(f"unsupported output format: {value!r}; expected one of {allowed}")
    return normalized


def validation_details(messages: Sequence[ValidationMessage]) -> list[dict[str, str]]:
    return [{"field": message.path, "issue": message.message} for message in messages]

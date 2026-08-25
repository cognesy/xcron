"""Shared helpers owned by the xcron-cli terminal channel.

The environment helpers that used to live here are gone. Host settings are
composed once by the selected settings provider and reach the channel through
the SDK; a CLI-local reader would be a second, competing answer.
"""

from __future__ import annotations

from typing import Sequence

from xcron.contracts import ValidationMessage

VALID_OUTPUT_FORMATS = ("json", "toon", "tmux")


def selected_output_format(value: str | None) -> str:
    normalized = (value or "toon").strip().lower()
    if normalized not in VALID_OUTPUT_FORMATS:
        allowed = ", ".join(VALID_OUTPUT_FORMATS)
        raise ValueError(f"unsupported output format: {value!r}; expected one of {allowed}")
    return normalized


def validation_details(messages: Sequence[ValidationMessage]) -> list[dict[str, str]]:
    return [{"field": message.path, "issue": message.message} for message in messages]

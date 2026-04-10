"""Common helpers for CLI command modules."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

from libs.domain import PlanChange, StatusEntry
from libs.services import (
    ValidationMessage,
    build_error_payload,
    parse_fields_csv,
    render_payload,
    render_toon,
)


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


def add_fields_argument(parser: object) -> None:
    """Add the standard AXI field-selection flag to one parser."""

    parser.add_argument(
        "--fields",
        help="Comma-separated list of response fields to include.",
    )


def add_full_argument(parser: object) -> None:
    """Add the standard AXI full-content flag to one parser."""

    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full response content instead of truncated previews.",
    )


def selected_fields(value: str | None) -> tuple[str, ...]:
    """Parse one optional --fields value into a tuple."""

    return parse_fields_csv(value)


def validation_details(messages: Sequence[ValidationMessage]) -> list[dict[str, str]]:
    """Convert validation messages into AXI error details."""

    return [{"field": message.path, "issue": message.message} for message in messages]


def emit_payload(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
) -> int:
    """Render one structured payload to stdout."""

    print(
        render_payload(
            payload,
            allowed_fields=allowed_fields,
            requested_fields=requested_fields,
        )
    )
    return 0


def emit_error(
    message: str,
    *,
    details: Sequence[dict[str, str]] = (),
    help_items: Sequence[str] = (),
    code: str = "runtime_error",
    exit_code: int = 1,
) -> int:
    """Render one structured error envelope to stdout."""

    print(
        render_toon(
            build_error_payload(
                message,
                code=code,
                details=details,
                help_items=help_items,
            )
        )
    )
    return exit_code


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

"""AXI-focused presentation helpers for xcron CLI shells."""

from __future__ import annotations

import os
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

from libs.services.toon_renderer import render_toon


def parse_fields_csv(value: str | None) -> tuple[str, ...]:
    """Parse one comma-separated field list into a stable tuple."""

    if value is None:
        return tuple()
    fields = []
    for item in value.split(","):
        field = item.strip()
        if field:
            fields.append(field)
    return tuple(fields)


def select_fields(
    payload: Mapping[str, Any],
    *,
    allowed_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
) -> dict[str, Any]:
    """Return one payload filtered to the allowed/requested field set."""

    allowed = tuple(allowed_fields)
    requested = tuple(field for field in requested_fields if field in allowed)
    active_fields = requested or allowed
    return {field: payload[field] for field in active_fields if field in payload}


def select_list_fields(
    payload: Mapping[str, Any],
    *,
    top_level_fields: Sequence[str],
    list_key: str,
    row_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
) -> dict[str, Any]:
    """Filter one list payload across top-level and row-level field sets."""

    requested = tuple(requested_fields)
    requested_top_level = tuple(field for field in requested if field in top_level_fields)
    requested_row_fields = tuple(field for field in requested if field in row_fields)
    if requested_row_fields and list_key not in requested_top_level:
        requested_top_level = requested_top_level + (list_key,)

    selected = select_fields(
        payload,
        allowed_fields=top_level_fields,
        requested_fields=requested_top_level,
    )
    if list_key in selected:
        selected[list_key] = [
            select_fields(row, allowed_fields=row_fields, requested_fields=requested_row_fields)
            for row in payload.get(list_key, ())
        ]
    return selected


def select_nested_fields(
    payload: Mapping[str, Any],
    *,
    top_level_fields: Sequence[str],
    nested_fields: Mapping[str, Sequence[str]],
    requested_fields: Sequence[str] = (),
) -> dict[str, Any]:
    """Filter one payload across top-level and dot-addressed nested fields."""

    requested = tuple(requested_fields)
    requested_top_level = [field for field in requested if field in top_level_fields]

    for parent_key in nested_fields:
        prefix = f"{parent_key}."
        if any(field.startswith(prefix) for field in requested) and parent_key not in requested_top_level:
            requested_top_level.append(parent_key)

    selected = select_fields(
        payload,
        allowed_fields=top_level_fields,
        requested_fields=tuple(requested_top_level),
    )

    for parent_key, allowed in nested_fields.items():
        if parent_key not in selected or not isinstance(selected[parent_key], Mapping):
            continue
        prefix = f"{parent_key}."
        nested_requested = tuple(
            field.removeprefix(prefix)
            for field in requested
            if field.startswith(prefix) and field.removeprefix(prefix) in allowed
        )
        selected[parent_key] = select_fields(
            selected[parent_key],
            allowed_fields=allowed,
            requested_fields=nested_requested,
        )

    return selected


def truncate_text(
    value: str,
    *,
    limit: int = 1000,
    full_hint: str | None = None,
) -> str | dict[str, Any]:
    """Return plain text or truncation metadata for large detail fields."""

    if len(value) <= limit:
        return value

    payload: dict[str, Any] = {
        "preview": value[:limit],
        "truncated": True,
        "total_chars": len(value),
    }
    if full_hint:
        payload["help"] = full_hint
    return payload


def build_error_payload(
    message: str,
    *,
    code: str,
    details: Sequence[Mapping[str, str]] = (),
    help_items: Sequence[str] = (),
) -> dict[str, Any]:
    """Build one common AXI error envelope."""

    payload: dict[str, Any] = {
        "kind": "error",
        "code": code,
        "message": message,
    }
    if details:
        payload["details"] = [dict(item) for item in details]
    if help_items:
        payload["help"] = list(help_items)
    return payload


def collapse_home_path(value: str | os.PathLike[str]) -> str:
    """Collapse the user's home directory to `~` for display."""

    path = str(Path(value).expanduser())
    home = str(Path.home())
    if path == home:
        return "~"
    if path.startswith(f"{home}{os.sep}"):
        return path.replace(home, "~", 1)
    return path


def render_payload(
    payload: Mapping[str, Any],
    *,
    allowed_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
) -> str:
    """Filter and render one simple payload."""

    return render_toon(
        select_fields(
            payload,
            allowed_fields=allowed_fields,
            requested_fields=requested_fields,
        )
    )


__all__ = [
    "build_error_payload",
    "collapse_home_path",
    "parse_fields_csv",
    "render_payload",
    "select_fields",
    "select_list_fields",
    "select_nested_fields",
    "truncate_text",
]

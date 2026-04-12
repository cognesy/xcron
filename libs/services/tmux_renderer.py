"""Compact tmux-pane renderer for xcron CLI output.

Produces concise, monitor-friendly text suitable for narrow tmux panes.
Scalars render as ``key: value`` lines. Lists render as aligned columns
with no decoration beyond a header count. Nested dicts are flattened.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def render_tmux(value: Any) -> str:
    """Render one normalized payload to compact tmux-pane text."""

    if not isinstance(value, Mapping):
        return str(value)

    lines: list[str] = []
    list_keys: list[str] = []

    for key, item in value.items():
        if _is_row_list(item):
            list_keys.append(key)
            continue
        if isinstance(item, Mapping):
            flat = _flatten_dict(item)
            if flat:
                lines.append(f"{key}: {flat}")
        else:
            lines.append(f"{key}: {_scalar(item)}")

    for key in list_keys:
        rows = value[key]
        if not rows:
            lines.append(f"{key}: (none)")
            continue
        rendered = _render_rows(rows)
        lines.append(f"{key}[{len(rows)}]:")
        lines.extend(f"  {row}" for row in rendered)

    return "\n".join(lines)


def _is_row_list(value: Any) -> bool:
    """True when *value* looks like a list of row dicts."""
    if not isinstance(value, (list, tuple)):
        return False
    return len(value) > 0 and isinstance(value[0], Mapping)


def _flatten_dict(mapping: Mapping[str, Any]) -> str:
    """Render a shallow dict as a compact ``k=v k=v`` string."""
    parts = []
    for key, item in mapping.items():
        parts.append(f"{key}={_scalar(item)}")
    return " ".join(parts)


def _scalar(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        if not value:
            return "-"
        return ",".join(str(item) for item in value)
    return str(value)


def _render_rows(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Render a list of row dicts as aligned columns."""
    if not rows:
        return []

    keys = list(rows[0].keys())
    col_values: list[list[str]] = [[_scalar(row.get(key)) for row in rows] for key in keys]
    col_widths = [max((len(cell) for cell in col), default=0) for col in col_values]

    rendered: list[str] = []
    for row_idx in range(len(rows)):
        cells = []
        for col_idx, key in enumerate(keys):
            cell = col_values[col_idx][row_idx]
            if col_idx < len(keys) - 1:
                cell = cell.ljust(col_widths[col_idx])
            cells.append(cell)
        rendered.append("  ".join(cells))
    return rendered


__all__ = ["render_tmux"]

"""Unified CLI output rendering for machine and human-facing paths."""

from __future__ import annotations

import json
import os
from io import StringIO
from collections.abc import Mapping
from typing import Sequence
from typing import Any, Literal

from rich.console import Console
from rich.markdown import Markdown

from libs.services.axi_presenter import (
    select_collection_fields,
    select_fields,
    select_list_fields,
    select_nested_fields,
)
from libs.services.toon_renderer import render_toon


OutputFormat = Literal["json", "toon"]


def normalize_for_output(value: Any) -> Any:
    """Normalize output payloads so TOON and JSON share one stable shape."""

    if isinstance(value, os.PathLike):
        return os.fspath(value)
    if isinstance(value, Mapping):
        return {str(key): normalize_for_output(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [normalize_for_output(item) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_for_output(item) for item in value]
    return value


def render_output(value: Any, *, output_format: OutputFormat = "toon") -> str:
    """Render one payload in the requested output format."""

    normalized = normalize_for_output(value)
    if output_format == "json":
        return json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=True)
    return render_toon(normalized)


def render_response(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
    output_format: OutputFormat = "toon",
) -> str:
    return render_output(
        select_fields(
            payload,
            allowed_fields=allowed_fields,
            requested_fields=requested_fields,
        ),
        output_format=output_format,
    )


def render_list_response(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    list_key: str,
    row_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
    output_format: OutputFormat = "toon",
) -> str:
    return render_output(
        select_list_fields(
            payload,
            top_level_fields=allowed_fields,
            list_key=list_key,
            row_fields=row_fields,
            requested_fields=requested_fields,
        ),
        output_format=output_format,
    )


def render_nested_response(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    nested_fields: dict[str, Sequence[str]],
    requested_fields: Sequence[str] = (),
    output_format: OutputFormat = "toon",
) -> str:
    return render_output(
        select_nested_fields(
            payload,
            top_level_fields=allowed_fields,
            nested_fields=nested_fields,
            requested_fields=requested_fields,
        ),
        output_format=output_format,
    )


def render_collection_response(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    collection_fields: dict[str, Sequence[str]],
    requested_fields: Sequence[str] = (),
    output_format: OutputFormat = "toon",
) -> str:
    return render_output(
        select_collection_fields(
            payload,
            top_level_fields=allowed_fields,
            collection_fields=collection_fields,
            requested_fields=requested_fields,
        ),
        output_format=output_format,
    )


def render_response_toon(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
) -> str:
    return render_response(
        payload,
        allowed_fields=allowed_fields,
        requested_fields=requested_fields,
        output_format="toon",
    )


def render_list_response_toon(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    list_key: str,
    row_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
) -> str:
    return render_list_response(
        payload,
        allowed_fields=allowed_fields,
        list_key=list_key,
        row_fields=row_fields,
        requested_fields=requested_fields,
        output_format="toon",
    )


def render_nested_response_toon(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    nested_fields: dict[str, Sequence[str]],
    requested_fields: Sequence[str] = (),
) -> str:
    return render_nested_response(
        payload,
        allowed_fields=allowed_fields,
        nested_fields=nested_fields,
        requested_fields=requested_fields,
        output_format="toon",
    )


def render_collection_response_toon(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    collection_fields: dict[str, Sequence[str]],
    requested_fields: Sequence[str] = (),
) -> str:
    return render_collection_response(
        payload,
        allowed_fields=allowed_fields,
        collection_fields=collection_fields,
        requested_fields=requested_fields,
        output_format="toon",
    )


def render_help_markdown(help_body: str, parser_help: str) -> str:
    """Render authored help through Rich markdown plus structured reference text."""

    parser_help = parser_help.strip()
    usage_block, _, remainder = parser_help.partition("\n\n")

    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, color_system=None, width=100)
    console.print(Markdown(help_body))
    if usage_block:
        console.print("\nUsage\n")
        console.print(usage_block)
    if remainder.strip():
        console.print("\nReference\n")
        console.print(remainder.strip())
    return buffer.getvalue().rstrip() + "\n"


__all__ = [
    "OutputFormat",
    "normalize_for_output",
    "render_collection_response",
    "render_collection_response_toon",
    "render_help_markdown",
    "render_list_response",
    "render_list_response_toon",
    "render_nested_response",
    "render_nested_response_toon",
    "render_output",
    "render_response",
    "render_response_toon",
]

"""Unified CLI output rendering for machine and human-facing paths."""

from __future__ import annotations

from io import StringIO
from typing import Sequence

from rich.console import Console
from rich.markdown import Markdown

from libs.services.axi_presenter import (
    select_collection_fields,
    select_fields,
    select_list_fields,
    select_nested_fields,
)
from libs.services.toon_renderer import render_toon


def render_response_toon(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
) -> str:
    return render_toon(
        select_fields(
            payload,
            allowed_fields=allowed_fields,
            requested_fields=requested_fields,
        )
    )


def render_list_response_toon(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    list_key: str,
    row_fields: Sequence[str],
    requested_fields: Sequence[str] = (),
) -> str:
    return render_toon(
        select_list_fields(
            payload,
            top_level_fields=allowed_fields,
            list_key=list_key,
            row_fields=row_fields,
            requested_fields=requested_fields,
        )
    )


def render_nested_response_toon(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    nested_fields: dict[str, Sequence[str]],
    requested_fields: Sequence[str] = (),
) -> str:
    return render_toon(
        select_nested_fields(
            payload,
            top_level_fields=allowed_fields,
            nested_fields=nested_fields,
            requested_fields=requested_fields,
        )
    )


def render_collection_response_toon(
    payload: dict[str, object],
    *,
    allowed_fields: Sequence[str],
    collection_fields: dict[str, Sequence[str]],
    requested_fields: Sequence[str] = (),
) -> str:
    return render_toon(
        select_collection_fields(
            payload,
            top_level_fields=allowed_fields,
            collection_fields=collection_fields,
            requested_fields=requested_fields,
        )
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
    "render_collection_response_toon",
    "render_help_markdown",
    "render_list_response_toon",
    "render_nested_response_toon",
    "render_response_toon",
]

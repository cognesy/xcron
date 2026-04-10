"""Backward-compatible help rendering wrapper."""

from __future__ import annotations

from importlib.resources import files

from libs.services.output_renderer import render_help_markdown


HELP_PACKAGE = "resources.help"


def load_help_body(help_key: str) -> str:
    """Load one authored help page from packaged resources."""

    resource = files(HELP_PACKAGE).joinpath(f"{help_key}.md")
    return resource.read_text(encoding="utf-8").strip()


def render_help_text(help_key: str, parser_help: str) -> str:
    """Load authored help and render it through the Rich-backed output service."""

    return render_help_markdown(load_help_body(help_key), parser_help)


__all__ = ["HELP_PACKAGE", "load_help_body", "render_help_text"]

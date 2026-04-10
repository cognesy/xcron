"""Backward-compatible help rendering wrapper."""

from __future__ import annotations

from importlib.resources import files
from io import StringIO

from rich.console import Console
from rich.markdown import Markdown


HELP_PACKAGE = "resources.help"


def load_help_body(help_key: str) -> str:
    """Load one authored help page from packaged resources."""

    resource = files(HELP_PACKAGE).joinpath(f"{help_key}.md")
    return resource.read_text(encoding="utf-8").strip()


def render_help_text(help_key: str, parser_help: str) -> str:
    """Load authored help and render it through the Rich-backed output service."""

    return render_help_markdown(load_help_body(help_key), parser_help)

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


__all__ = ["HELP_PACKAGE", "load_help_body", "render_help_markdown", "render_help_text"]

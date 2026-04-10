"""Resource-backed help rendering for the xcron CLI."""

from __future__ import annotations

from importlib.resources import files


HELP_PACKAGE = "resources.help"


def load_help_body(help_key: str) -> str:
    """Load one authored help page from packaged resources."""

    resource = files(HELP_PACKAGE).joinpath(f"{help_key}.md")
    return resource.read_text(encoding="utf-8").strip()


def render_help_text(help_key: str, parser_help: str) -> str:
    """Combine authored help content with parser-generated reference text."""

    return f"{load_help_body(help_key)}\n\n{parser_help}"


__all__ = ["HELP_PACKAGE", "load_help_body", "render_help_text"]

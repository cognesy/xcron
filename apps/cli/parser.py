"""AXI-aware parser helpers for the xcron CLI."""

from __future__ import annotations

import argparse
import sys

from libs.services import build_error_payload, render_help_text, render_toon


class AxiArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that emits structured usage errors on stdout."""

    help_key: str | None = None

    def format_help(self) -> str:
        parser_help = super().format_help()
        if not self.help_key:
            return parser_help
        return render_help_text(self.help_key, parser_help)

    def error(self, message: str) -> None:
        payload = build_error_payload(
            message,
            code="usage_error",
            help_items=(f"Run `{self.prog} --help` to see available commands",),
        )
        sys.stdout.write(f"{render_toon(payload)}\n")
        raise SystemExit(2)


def set_help_key(parser: argparse.ArgumentParser, help_key: str) -> argparse.ArgumentParser:
    """Attach one packaged help key to a parser instance."""

    setattr(parser, "help_key", help_key)
    return parser


__all__ = ["AxiArgumentParser", "set_help_key"]

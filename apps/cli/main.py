"""Compatibility wrapper around the Typer-based xcron CLI."""

from __future__ import annotations

import sys
from typing import Sequence

from click import ClickException
from click.exceptions import Exit as ClickExit
from typer.main import get_command

from apps.cli.typer_app import app


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Typer app for programmatic callers without test helpers."""

    command = get_command(app)
    try:
        result = command.main(args=list(argv or []), prog_name="xcron", standalone_mode=False)
        return int(result or 0)
    except ClickException as exc:
        exc.show(file=sys.stdout)
        return exc.exit_code
    except ClickExit as exc:
        return exc.exit_code

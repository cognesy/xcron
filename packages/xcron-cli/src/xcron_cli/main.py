"""The installed console-script and programmatic invocation boundary."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from click import ClickException
from click.exceptions import Exit as ClickExit
from typer.main import get_command


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with explicit arguments and return its process exit code.

    This is useful to embedded callers and keeps tests on the installed
    terminal package rather than depending on a legacy channel module.
    """
    from xcron_cli.typer_app import app

    command = get_command(app)
    try:
        result = command.main(args=list(argv or []), prog_name="xcron", standalone_mode=False)
        return int(result or 0)
    except ClickException as error:
        error.show(file=sys.stdout)
        return error.exit_code
    except ClickExit as error:
        return error.exit_code


def run() -> None:
    """Run the installed console script."""
    raise SystemExit(main(sys.argv[1:]))

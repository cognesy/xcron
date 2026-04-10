"""Compatibility wrapper around the Typer-based xcron CLI."""

from __future__ import annotations

import sys
from typing import Sequence

from typer.testing import CliRunner

from apps.cli.typer_app import app


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Typer app for programmatic callers and tests."""

    result = CliRunner(mix_stderr=False).invoke(app, list(argv or []), prog_name="xcron")
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.exit_code

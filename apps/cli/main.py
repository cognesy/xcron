"""CLI entrypoint for the xcron prototype."""

from __future__ import annotations

import argparse
from typing import Callable, Sequence

from apps.cli.commands import apply, inspect, jobs, plan, prune, status, validate
from libs.services import configure_logging

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xcron",
        description="Manage one project schedule under resources/schedules/ against native OS schedulers.",
    )
    parser.add_argument(
        "--project",
        help="Path to the project root containing resources/schedules/. Defaults to the current directory.",
    )
    parser.add_argument(
        "--schedule",
        help="Schedule name under resources/schedules/, without requiring the .yaml suffix.",
    )
    parser.add_argument(
        "--backend",
        choices=("launchd", "cron"),
        help="Override the backend instead of using the platform default.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    register_commands: Sequence[Callable[..., None]] = (
        validate.register,
        plan.register,
        apply.register,
        status.register,
        inspect.register,
        jobs.register,
        prune.register,
    )
    for register in register_commands:
        register(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error("no command handler registered")
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

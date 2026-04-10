"""CLI entrypoint for the xcron prototype."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
from typing import Callable, Sequence

from apps.cli.commands import apply, hooks, inspect, jobs, plan, prune, status, validate
from apps.cli.commands._common import emit_collection_response, emit_error, env_path, resolve_project_path, selected_contract_fields, validation_details
from apps.cli.parser import AxiArgumentParser, set_help_key
from libs.actions import plan_project
from libs.services import ensure_agent_hooks, get_command_contract, map_home_response

from libs.services import configure_logging

HOME_CONTRACT = get_command_contract("home")

def build_parser() -> argparse.ArgumentParser:
    parser = set_help_key(
        AxiArgumentParser(
            prog="xcron",
            description="Manage one project schedule under resources/schedules/ against native OS schedulers.",
        ),
        HOME_CONTRACT.help_key,
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
    parser.add_argument(
        "--fields",
        help="Comma-separated list of response fields to include when the selected command supports field filtering.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full response content instead of truncated previews when the selected command supports it.",
    )

    subparsers = parser.add_subparsers(dest="command", required=False)
    register_commands: Sequence[Callable[..., None]] = (
        validate.register,
        plan.register,
        apply.register,
        status.register,
        inspect.register,
        jobs.register,
        prune.register,
        hooks.register,
    )
    for register in register_commands:
        register(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    _auto_install_hooks_if_supported()
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        return handle_home(args)
    return int(handler(args))


def handle_home(args: argparse.Namespace) -> int:
    """Render the top-level xcron home view."""

    result = plan_project(
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
        backend=getattr(args, "backend", None),
        state_root=env_path("XCRON_STATE_ROOT"),
    )
    if not result.valid or result.plan is None or result.validation.normalized_manifest is None:
        return emit_error(
            "project home view unavailable because validation failed",
            details=validation_details(result.validation.errors + result.validation.warnings),
            help_items=("Run `xcron validate` to inspect manifest issues",),
        )

    response = map_home_response(
        result,
        executable=shutil.which("xcron") or "xcron",
        contract=HOME_CONTRACT,
        include_plan_changes=getattr(args, "full", False),
    )

    try:
        requested_fields = selected_contract_fields(HOME_CONTRACT, getattr(args, "fields", None))
    except ValueError as exc:
        return emit_error(str(exc), code="usage_error", exit_code=2, help_items=HOME_CONTRACT.default_hints)

    return emit_collection_response(
        response,
        allowed_fields=HOME_CONTRACT.allowed_fields,
        collection_fields=HOME_CONTRACT.collection_fields,
        requested_fields=requested_fields,
    )


def _auto_install_hooks_if_supported() -> None:
    """Best-effort hook self-install for real CLI sessions."""

    cwd = Path.cwd()
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    if not ((cwd / ".git").exists() or (cwd / "AGENTS.md").exists() or (cwd / "pyproject.toml").exists()):
        return
    try:
        ensure_agent_hooks(cwd)
    except Exception:
        # Hook installation must never break normal CLI behavior.
        return


if __name__ == "__main__":
    raise SystemExit(main())

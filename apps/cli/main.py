"""CLI entrypoint for the xcron prototype."""

from __future__ import annotations

import argparse
from collections import Counter
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Sequence

from apps.cli.commands import apply, hooks, inspect, jobs, plan, prune, status, validate
from apps.cli.commands._common import emit_error, env_path, resolve_project_path, selected_fields, validation_details
from apps.cli.parser import AxiArgumentParser, set_help_key
from libs.actions import plan_project
from libs.services import collapse_home_path, ensure_agent_hooks, render_toon, select_fields

from libs.services import configure_logging


HOME_FIELDS = ("bin", "description", "project", "schedule", "backend", "manifest", "jobs", "plan_summary", "plan_changes", "help")
PLAN_CHANGE_FIELDS = ("kind", "id", "reason")

def build_parser() -> argparse.ArgumentParser:
    parser = set_help_key(
        AxiArgumentParser(
            prog="xcron",
            description="Manage one project schedule under resources/schedules/ against native OS schedulers.",
        ),
        "root",
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

    executable = shutil.which("xcron") or sys.argv[0]
    counts = Counter(change.kind.value for change in result.changes)
    payload: dict[str, object] = {
        "bin": collapse_home_path(executable),
        "description": "Manage project-local schedules against native OS schedulers",
        "project": result.validation.project_root,
        "schedule": Path(result.validation.manifest_path).stem if result.validation.manifest_path else None,
        "backend": result.backend,
        "manifest": result.validation.manifest_path,
        "jobs": {"total": len(result.validation.normalized_manifest.jobs)},
        "plan_summary": [{"kind": kind, "count": count} for kind, count in sorted(counts.items())],
        "help": [
            "Run `xcron validate` to confirm manifest validity",
            "Run `xcron plan` to preview scheduler changes",
            "Run `xcron status` to inspect actual backend state",
        ],
    }
    if getattr(args, "full", False):
        payload["plan_changes"] = [
            {"kind": change.kind.value, "id": change.qualified_id, "reason": change.reason}
            for change in result.changes
        ]

    requested = selected_fields(getattr(args, "fields", None))
    selected_payload = select_fields(
        payload,
        allowed_fields=HOME_FIELDS,
        requested_fields=requested,
    )
    if "plan_changes" in selected_payload:
        selected_payload["plan_changes"] = [
            select_fields(row, allowed_fields=PLAN_CHANGE_FIELDS)
            for row in payload["plan_changes"]  # type: ignore[index]
        ]
    if "plan_summary" in selected_payload:
        selected_payload["plan_summary"] = [
            select_fields(row, allowed_fields=("kind", "count"))
            for row in payload["plan_summary"]  # type: ignore[index]
        ]
    print(render_toon(selected_payload))
    return 0


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

"""Internal hook command shells for agent session integration."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from apps.cli.commands._common import emit_error
from libs.actions import plan_project
from libs.services import capture_session_end, collapse_home_path, ensure_agent_hooks, inspect_agent_hooks, render_toon, resolve_xcron_executable


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("hooks", help="Manage repo-local Codex and Claude hook integration.")
    hooks_subparsers = parser.add_subparsers(dest="hooks_command", required=True)

    install_parser = hooks_subparsers.add_parser("install", help="Install or update repo-local hook configuration.")
    install_parser.set_defaults(handler=handle_install)

    status_parser = hooks_subparsers.add_parser("status", help="Inspect repo-local hook status and path health.")
    status_parser.set_defaults(handler=handle_status)

    repair_parser = hooks_subparsers.add_parser("repair", help="Repair repo-local hook configuration and executable paths.")
    repair_parser.set_defaults(handler=handle_repair)

    start_parser = hooks_subparsers.add_parser("session-start", help=argparse.SUPPRESS)
    start_parser.set_defaults(handler=handle_session_start)

    end_parser = hooks_subparsers.add_parser("session-end", help=argparse.SUPPRESS)
    end_parser.set_defaults(handler=handle_session_end)


def handle_install(args: argparse.Namespace) -> int:
    result = ensure_agent_hooks(Path.cwd())
    print(
        render_toon(
            {
                "kind": "hooks.install",
                "changed": len(result.changed_files),
                "files": result.changed_files,
            }
        )
    )
    return 0


def handle_status(args: argparse.Namespace) -> int:
    result = inspect_agent_hooks(Path.cwd())
    print(
        render_toon(
            {
                "kind": "hooks.status",
                "executable": result.executable_path,
                "codex": {
                    "config_path": result.codex.config_path,
                    "hooks_path": result.codex.hooks_path,
                    "config_exists": result.codex.config_exists,
                    "hooks_exists": result.codex.hooks_exists,
                    "feature_enabled": result.codex.feature_enabled,
                    "session_start_matches": result.codex.session_start_matches,
                    "session_end_matches": result.codex.session_end_matches,
                },
                "claude": {
                    "settings_path": result.claude.settings_path,
                    "settings_exists": result.claude.settings_exists,
                    "session_start_matches": result.claude.session_start_matches,
                    "stop_matches": result.claude.stop_matches,
                },
            }
        )
    )
    return 0


def handle_repair(args: argparse.Namespace) -> int:
    return handle_install(args)


def handle_session_start(args: argparse.Namespace) -> int:
    result = plan_project(Path.cwd(), state_root=None)
    if not result.valid or result.plan is None or result.validation.normalized_manifest is None:
        return emit_error("session-start context unavailable", help_items=("Run `xcron validate` in this project",))

    counts = Counter(change.kind.value for change in result.changes)
    payload = {
        "bin": collapse_home_path(resolve_xcron_executable()),
        "project": result.validation.project_root,
        "manifest": result.validation.manifest_path,
        "backend": result.backend,
        "jobs": len(result.validation.normalized_manifest.jobs),
        "plan_summary": [{"kind": kind, "count": count} for kind, count in sorted(counts.items())],
        "help": [
            "Run `xcron plan` to inspect full scheduler changes",
            "Run `xcron status` to inspect actual backend state",
        ],
    }
    print(render_toon(payload))
    return 0


def handle_session_end(args: argparse.Namespace) -> int:
    log_path = capture_session_end(Path.cwd())
    print(render_toon({"kind": "hooks.session_end", "log": str(log_path)}))
    return 0

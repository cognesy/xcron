"""Apply command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import env_flag, env_path, env_string, print_plan_changes, print_validation_messages, resolve_project_path
from libs.actions import apply_project


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("apply", help="Apply one selected schedule manifest.")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = apply_project(
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
        backend=getattr(args, "backend", None),
        state_root=env_path("XCRON_STATE_ROOT"),
        launch_agents_dir=env_path("XCRON_LAUNCH_AGENTS_DIR"),
        launchctl_domain=env_string("XCRON_LAUNCHCTL_DOMAIN"),
        crontab_path=env_path("XCRON_CRONTAB_PATH"),
        manage_launchctl=env_flag("XCRON_MANAGE_LAUNCHCTL", default=True),
        manage_crontab=env_flag("XCRON_MANAGE_CRONTAB", default=True),
    )
    if not result.valid:
        print_validation_messages(result.plan_result.validation.errors)
        print_validation_messages(result.plan_result.validation.warnings)
        return 2
    print(f"backend: {result.backend}")
    print_plan_changes(result.plan_result.changes)
    print(f"applied_jobs: {len(result.applied_state.jobs) if result.applied_state else 0}")
    return 0

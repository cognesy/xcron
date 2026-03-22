"""Status command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import env_path, env_string, print_status_entries, print_validation_messages, resolve_project_path
from libs.actions import status_project


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("status", help="Show deployed status for one selected schedule manifest.")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = status_project(
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
        backend=getattr(args, "backend", None),
        launch_agents_dir=env_path("XCRON_LAUNCH_AGENTS_DIR"),
        launchctl_domain=env_string("XCRON_LAUNCHCTL_DOMAIN"),
        crontab_path=env_path("XCRON_CRONTAB_PATH"),
    )
    if not result.valid or result.plan is None:
        print_validation_messages(result.validation.errors)
        print_validation_messages(result.validation.warnings)
        return 2
    print(f"backend: {result.backend}")
    print_status_entries(result.statuses)
    return 0

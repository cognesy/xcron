"""Plan command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import env_path, print_plan_changes, print_validation_messages, resolve_project_path
from libs.actions import plan_project


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("plan", help="Show planned scheduler changes for one schedule manifest.")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = plan_project(
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
        backend=getattr(args, "backend", None),
        state_root=env_path("XCRON_STATE_ROOT"),
    )
    if not result.valid:
        print_validation_messages(result.validation.errors)
        print_validation_messages(result.validation.warnings)
        return 2
    print(f"backend: {result.backend}")
    print(f"state: {result.state_path}")
    print_plan_changes(result.changes)
    return 0

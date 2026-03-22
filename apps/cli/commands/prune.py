"""Prune command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import env_flag, env_path, env_string, resolve_project_path
from libs.actions import prune_project


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("prune", help="Remove managed artifacts for one selected schedule manifest.")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = prune_project(
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
        if result.error:
            print(result.error)
        return 2
    print(f"backend: {result.backend}")
    print(f"removed: {len(result.removed)}")
    return 0

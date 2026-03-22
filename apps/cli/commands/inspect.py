"""Inspect command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import env_path, env_string, print_validation_messages, resolve_project_path
from libs.actions import inspect_job


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("inspect", help="Inspect one managed job.")
    parser.add_argument("job_id", help="Project-local or qualified job identifier.")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = inspect_job(
        args.job_id,
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
        backend=getattr(args, "backend", None),
        launch_agents_dir=env_path("XCRON_LAUNCH_AGENTS_DIR"),
        launchctl_domain=env_string("XCRON_LAUNCHCTL_DOMAIN"),
        crontab_path=env_path("XCRON_CRONTAB_PATH"),
    )
    if not result.valid:
        if result.status.validation.errors:
            print_validation_messages(result.status.validation.errors)
        if result.error:
            print(result.error)
        return 2
    print(f"backend: {result.backend}")
    if result.desired_fields:
        print("desired:")
        for field in result.desired_fields:
            print(f"  {field.name}: {field.value}")
    if result.deployed_fields:
        print("deployed:")
        for field in result.deployed_fields:
            print(f"  {field.name}: {field.value}")
    for snippet in result.snippets:
        print(f"{snippet.name}:")
        print(snippet.content)
    return 0

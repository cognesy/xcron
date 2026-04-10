"""Status command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import (
    add_fields_argument,
    emit_error,
    env_path,
    env_string,
    resolve_project_path,
    selected_fields,
    validation_details,
)
from apps.cli.parser import set_help_key
from libs.actions import status_project
from libs.services import render_toon, select_list_fields


STATUS_FIELDS = ("backend", "count", "statuses", "help")
STATUS_ROW_FIELDS = ("kind", "id", "reason")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("status", help="Show deployed status for one selected schedule manifest."),
        "status",
    )
    add_fields_argument(parser)
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
        return emit_error(
            "project status inspection failed",
            details=validation_details(result.validation.errors + result.validation.warnings),
            help_items=("Run `xcron validate` to resolve manifest issues",),
        )

    payload = {
        "backend": result.backend,
        "count": f"{len(result.statuses)} of {len(result.statuses)}",
        "statuses": [
            {
                "kind": entry.kind.value,
                "id": entry.qualified_id,
                "reason": entry.reason,
            }
            for entry in result.statuses
        ],
        "help": [
            "Run `xcron inspect <job-id>` for one detailed job view",
            "Run `xcron apply` to reconcile drift or missing jobs",
        ],
    }
    print(
        render_toon(
            select_list_fields(
                payload,
                top_level_fields=STATUS_FIELDS,
                list_key="statuses",
                row_fields=STATUS_ROW_FIELDS,
                requested_fields=selected_fields(getattr(args, "fields", None)),
            )
        )
    )
    return 0

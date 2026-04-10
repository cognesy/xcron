"""Plan command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import add_fields_argument, emit_error, env_path, resolve_project_path, selected_fields, validation_details
from apps.cli.parser import set_help_key
from libs.actions import plan_project
from libs.services import render_toon, select_list_fields


PLAN_FIELDS = ("backend", "state", "count", "changes", "help")
PLAN_CHANGE_FIELDS = ("kind", "id", "reason")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("plan", help="Show planned scheduler changes for one schedule manifest."),
        "plan",
    )
    add_fields_argument(parser)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = plan_project(
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
        backend=getattr(args, "backend", None),
        state_root=env_path("XCRON_STATE_ROOT"),
    )
    if not result.valid:
        return emit_error(
            "project planning failed",
            details=validation_details(result.validation.errors + result.validation.warnings),
            help_items=("Run `xcron validate` to inspect manifest issues first",),
        )

    payload = {
        "backend": result.backend,
        "state": result.state_path,
        "count": f"{len(result.changes)} of {len(result.changes)}",
        "changes": [
            {
                "kind": change.kind.value,
                "id": change.qualified_id,
                "reason": change.reason,
            }
            for change in result.changes
        ],
        "help": [
            "Run `xcron apply` to reconcile the selected manifest",
            "Run `xcron status` to inspect actual deployed backend state",
        ],
    }
    print(
        render_toon(
            select_list_fields(
                payload,
                top_level_fields=PLAN_FIELDS,
                list_key="changes",
                row_fields=PLAN_CHANGE_FIELDS,
                requested_fields=selected_fields(getattr(args, "fields", None)),
            )
        )
    )
    return 0

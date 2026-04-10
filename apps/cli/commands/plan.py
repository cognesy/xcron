"""Plan command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import add_fields_argument, emit_error, emit_list_response, env_path, resolve_project_path, selected_contract_fields, validation_details
from apps.cli.parser import set_help_key
from libs.actions import plan_project
from libs.services import get_command_contract, map_plan_response


CONTRACT = get_command_contract("plan")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("plan", help="Show planned scheduler changes for one schedule manifest."),
        CONTRACT.help_key,
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
            help_items=CONTRACT.default_hints,
        )

    try:
        requested_fields = selected_contract_fields(CONTRACT, getattr(args, "fields", None))
    except ValueError as exc:
        return emit_error(str(exc), code="usage_error", exit_code=2, help_items=CONTRACT.default_hints)

    return emit_list_response(
        map_plan_response(result, contract=CONTRACT),
        allowed_fields=CONTRACT.allowed_fields,
        list_key=CONTRACT.list_key or "changes",
        row_fields=CONTRACT.list_row_fields,
        requested_fields=requested_fields,
    )

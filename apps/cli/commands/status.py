"""Status command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import (
    add_fields_argument,
    emit_error,
    emit_list_response,
    env_path,
    env_string,
    resolve_project_path,
    selected_contract_fields,
    validation_details,
)
from apps.cli.parser import set_help_key
from libs.actions import status_project
from libs.services import get_command_contract, map_status_response


CONTRACT = get_command_contract("status")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("status", help="Show deployed status for one selected schedule manifest."),
        CONTRACT.help_key,
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
            help_items=CONTRACT.default_hints,
        )

    try:
        requested_fields = selected_contract_fields(CONTRACT, getattr(args, "fields", None))
    except ValueError as exc:
        return emit_error(str(exc), code="usage_error", exit_code=2, help_items=CONTRACT.default_hints)

    return emit_list_response(
        map_status_response(result, contract=CONTRACT),
        allowed_fields=CONTRACT.allowed_fields,
        list_key=CONTRACT.list_key or "statuses",
        row_fields=CONTRACT.list_row_fields,
        requested_fields=requested_fields,
    )

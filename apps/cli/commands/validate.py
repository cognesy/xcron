"""Validate command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import add_fields_argument, emit_error, emit_response, resolve_project_path, selected_contract_fields, validation_details
from apps.cli.parser import set_help_key
from libs.actions import validate_project
from libs.services import get_command_contract, map_validation_response


CONTRACT = get_command_contract("validate")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("validate", help="Validate one schedule manifest under resources/schedules/."),
        CONTRACT.help_key,
    )
    add_fields_argument(parser)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = validate_project(
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
    )
    if not result.valid or result.hashes is None or result.normalized_manifest is None:
        return emit_error(
            "project validation failed",
            details=validation_details(result.errors + result.warnings),
            help_items=CONTRACT.default_hints,
        )

    try:
        requested_fields = selected_contract_fields(CONTRACT, getattr(args, "fields", None))
    except ValueError as exc:
        return emit_error(str(exc), code="usage_error", exit_code=2, help_items=CONTRACT.default_hints)

    return emit_response(
        map_validation_response(result),
        allowed_fields=CONTRACT.allowed_fields,
        requested_fields=requested_fields,
    )

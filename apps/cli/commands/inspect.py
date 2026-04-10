"""Inspect command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import add_fields_argument, add_full_argument, emit_error, emit_nested_response, env_path, env_string, resolve_project_path, selected_contract_fields, validation_details
from apps.cli.parser import set_help_key
from libs.actions import inspect_job
from libs.services import get_command_contract, map_inspect_response


CONTRACT = get_command_contract("inspect")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("inspect", help="Inspect one managed job."),
        CONTRACT.help_key,
    )
    parser.add_argument("job_id", help="Project-local or qualified job identifier.")
    add_fields_argument(parser)
    add_full_argument(parser)
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
        details = validation_details(result.status.validation.errors + result.status.validation.warnings)
        if result.error and not details:
            details = [{"field": "job_id", "issue": result.error}]
        return emit_error(
            result.error or "job inspection failed",
            details=details,
            help_items=CONTRACT.default_hints,
        )

    try:
        requested_fields = selected_contract_fields(CONTRACT, getattr(args, "fields", None))
    except ValueError as exc:
        return emit_error(str(exc), code="usage_error", exit_code=2, help_items=CONTRACT.default_hints)

    return emit_nested_response(
        map_inspect_response(
            result,
            contract=CONTRACT,
            job_id=args.job_id,
            full=getattr(args, "full", False),
        ),
        allowed_fields=CONTRACT.allowed_fields,
        nested_fields=CONTRACT.nested_fields,
        requested_fields=requested_fields,
    )

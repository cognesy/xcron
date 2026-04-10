"""Prune command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import add_fields_argument, emit_error, emit_response, env_flag, env_path, env_string, resolve_project_path, selected_contract_fields
from apps.cli.parser import set_help_key
from libs.actions import prune_project
from libs.services import get_command_contract, map_prune_response


CONTRACT = get_command_contract("prune")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("prune", help="Remove managed artifacts for one selected schedule manifest."),
        CONTRACT.help_key,
    )
    add_fields_argument(parser)
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
        return emit_error(
            result.error or "project prune failed",
            help_items=CONTRACT.default_hints,
        )

    try:
        requested_fields = selected_contract_fields(CONTRACT, getattr(args, "fields", None))
    except ValueError as exc:
        return emit_error(str(exc), code="usage_error", exit_code=2, help_items=CONTRACT.default_hints)

    return emit_response(
        map_prune_response(result, contract=CONTRACT),
        allowed_fields=CONTRACT.allowed_fields,
        requested_fields=requested_fields,
    )

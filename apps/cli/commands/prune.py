"""Prune command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import add_fields_argument, emit_error, emit_payload, env_flag, env_path, env_string, resolve_project_path, selected_fields
from apps.cli.parser import set_help_key
from libs.actions import prune_project


PRUNE_FIELDS = ("kind", "target", "outcome", "backend", "count", "help")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("prune", help="Remove managed artifacts for one selected schedule manifest."),
        "prune",
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
            help_items=("Run `xcron prune --help` to review prune usage",),
        )

    payload = {
        "kind": "prune",
        "target": result.project_id,
        "outcome": "noop" if not result.removed else "pruned",
        "backend": result.backend,
        "count": len(result.removed),
        "help": [
            "Run `xcron apply` to recreate managed backend state from the manifest",
        ],
    }
    return emit_payload(
        payload,
        allowed_fields=PRUNE_FIELDS,
        requested_fields=selected_fields(getattr(args, "fields", None)),
    )

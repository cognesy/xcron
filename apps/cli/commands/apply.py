"""Apply command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import add_fields_argument, emit_error, emit_payload, env_flag, env_path, env_string, resolve_project_path, selected_fields, validation_details
from apps.cli.parser import set_help_key
from libs.actions import apply_project


APPLY_FIELDS = ("kind", "target", "outcome", "backend", "count", "manifest", "help")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("apply", help="Apply one selected schedule manifest."),
        "apply",
    )
    add_fields_argument(parser)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = apply_project(
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
            "project apply failed",
            details=validation_details(result.plan_result.validation.errors + result.plan_result.validation.warnings),
            help_items=("Run `xcron plan` to inspect the current change set",),
        )

    non_noop_changes = [change for change in result.plan_result.changes if change.kind.value != "noop"]
    payload = {
        "kind": "apply",
        "target": result.plan_result.validation.normalized_manifest.project_id,
        "outcome": "noop" if not non_noop_changes else "applied",
        "backend": result.backend,
        "count": len(non_noop_changes),
        "manifest": result.plan_result.validation.manifest_path,
        "help": [
            "Run `xcron status` to confirm deployed backend state",
            "Run `xcron inspect <job-id>` for one detailed post-apply view",
        ],
    }
    return emit_payload(
        payload,
        allowed_fields=APPLY_FIELDS,
        requested_fields=selected_fields(getattr(args, "fields", None)),
    )

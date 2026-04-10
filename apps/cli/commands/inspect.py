"""Inspect command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import add_fields_argument, add_full_argument, emit_error, env_path, env_string, resolve_project_path, selected_fields, validation_details
from apps.cli.parser import set_help_key
from libs.actions import inspect_job
from libs.services import render_toon, select_nested_fields, truncate_text


INSPECT_FIELDS = ("backend", "job", "status", "desired", "deployed", "snippets", "help")
DESIRED_FIELDS = ("qualified_id", "job_id", "status", "schedule", "enabled", "command", "working_dir", "shell", "overlap", "description", "timezone", "env")
DEPLOYED_FIELDS = ("qualified_id", "backend_enabled", "desired_hash", "definition_hash", "label", "artifact_path", "wrapper_path", "stdout_log", "stderr_log", "loaded")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("inspect", help="Inspect one managed job."),
        "inspect",
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
            help_items=("Run `xcron inspect --help` to review inspect usage",),
        )

    payload = {
        "backend": result.backend,
        "job": result.desired_job.qualified_id if result.desired_job is not None else args.job_id,
        "status": result.status_entry.kind.value if result.status_entry is not None else "unknown",
        "desired": {field.name: field.value for field in result.desired_fields},
        "deployed": {field.name: field.value for field in result.deployed_fields},
        "snippets": {
            snippet.name: (
                snippet.content
                if getattr(args, "full", False)
                else truncate_text(
                    snippet.content,
                    full_hint=f"Run `xcron inspect {args.job_id} --full` to see complete content",
                )
            )
            for snippet in result.snippets
        },
        "help": ["Run `xcron status` to compare the full project against backend state"],
    }
    print(
        render_toon(
            select_nested_fields(
                payload,
                top_level_fields=INSPECT_FIELDS,
                nested_fields={
                    "desired": DESIRED_FIELDS,
                    "deployed": DEPLOYED_FIELDS,
                },
                requested_fields=selected_fields(getattr(args, "fields", None)),
            )
        )
    )
    return 0

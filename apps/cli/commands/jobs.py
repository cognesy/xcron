"""Job-level manifest management command shells."""

from __future__ import annotations

import argparse
from typing import Any, Sequence

from apps.cli.commands._common import (
    add_fields_argument,
    add_full_argument,
    emit_error,
    emit_payload,
    resolve_project_path,
    selected_fields,
    validation_details,
)
from apps.cli.parser import set_help_key
from libs.actions import add_job, disable_job, enable_job, list_jobs, remove_job, show_job, update_job
from libs.services import render_toon, select_list_fields


JOBS_LIST_FIELDS = ("manifest", "count", "jobs", "help")
JOBS_LIST_ROW_FIELDS = ("job_id", "enabled", "schedule", "command")
JOB_SHOW_FIELDS = ("manifest", "job", "enabled", "schedule", "command", "working_dir", "shell", "overlap", "description", "env", "help")
JOB_MUTATION_FIELDS = ("kind", "target", "outcome", "manifest", "help")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser(
            "jobs",
            help="Inspect and edit jobs inside one schedule manifest. These commands change YAML only.",
            description="Inspect and edit jobs inside one selected schedule manifest. These commands edit YAML only; use apply to reconcile backend state.",
        ),
        "jobs/index",
    )
    jobs_subparsers = parser.add_subparsers(dest="jobs_command", required=True)

    list_parser = set_help_key(
        jobs_subparsers.add_parser(
            "list",
            help="List jobs from the selected manifest.",
            description="List jobs from the selected manifest without touching the scheduler backend.",
        ),
        "jobs/list",
    )
    add_fields_argument(list_parser)
    list_parser.set_defaults(handler=handle_list)

    show_parser = set_help_key(
        jobs_subparsers.add_parser(
            "show",
            help="Show one job from the selected manifest.",
            description="Show one manifest job by local or qualified id without touching the scheduler backend.",
        ),
        "jobs/show",
    )
    show_parser.add_argument("job_id", help="Project-local or qualified job identifier.")
    add_fields_argument(show_parser)
    add_full_argument(show_parser)
    show_parser.set_defaults(handler=handle_show)

    add_parser = set_help_key(
        jobs_subparsers.add_parser(
            "add",
            help="Add one job to the selected manifest.",
            description="Add one job to the selected manifest. This edits YAML only; run apply separately to reconcile backend state.",
        ),
        "jobs/add",
    )
    add_parser.add_argument("job_id", help="Project-local job identifier to add.")
    add_parser.add_argument("--command", required=True, help="Shell command for the new job.")
    add_schedule = add_parser.add_mutually_exclusive_group(required=True)
    add_schedule.add_argument("--cron", help="Cron expression for the new job.")
    add_schedule.add_argument("--every", help="Portable interval string such as 15m or 1h.")
    add_parser.add_argument("--description", help="Optional human description.")
    add_parser.add_argument("--working-dir", help="Optional job-specific working directory.")
    add_parser.add_argument("--shell", help="Optional job-specific shell.")
    add_parser.add_argument("--overlap", choices=("allow", "forbid"), help="Optional overlap policy override.")
    add_parser.add_argument("--env", action="append", default=[], metavar="KEY=VALUE", help="Environment variable assignment. Repeatable.")
    add_parser.add_argument("--disabled", action="store_true", help="Create the job as disabled in YAML.")
    add_fields_argument(add_parser)
    add_parser.set_defaults(handler=handle_add)

    remove_parser = set_help_key(
        jobs_subparsers.add_parser(
            "remove",
            help="Remove one job from the selected manifest.",
            description="Remove one job from the selected manifest. This edits YAML only; it does not prune the scheduler backend.",
        ),
        "jobs/remove",
    )
    remove_parser.add_argument("job_id", help="Project-local or qualified job identifier.")
    add_fields_argument(remove_parser)
    remove_parser.set_defaults(handler=handle_remove)

    enable_parser = set_help_key(
        jobs_subparsers.add_parser(
            "enable",
            help="Enable one job in the selected manifest.",
            description="Enable one manifest job in YAML only. Use apply separately to reconcile backend state.",
        ),
        "jobs/enable",
    )
    enable_parser.add_argument("job_id", help="Project-local or qualified job identifier.")
    add_fields_argument(enable_parser)
    enable_parser.set_defaults(handler=handle_enable)

    disable_parser = set_help_key(
        jobs_subparsers.add_parser(
            "disable",
            help="Disable one job in the selected manifest.",
            description="Disable one manifest job in YAML only. Use apply separately to reconcile backend state.",
        ),
        "jobs/disable",
    )
    disable_parser.add_argument("job_id", help="Project-local or qualified job identifier.")
    add_fields_argument(disable_parser)
    disable_parser.set_defaults(handler=handle_disable)

    update_parser = set_help_key(
        jobs_subparsers.add_parser(
            "update",
            help="Update selected fields for one job in the selected manifest.",
            description="Update selected manifest fields for one job. This edits YAML only; use apply separately to reconcile backend state.",
        ),
        "jobs/update",
    )
    update_parser.add_argument("job_id", help="Project-local or qualified job identifier.")
    update_parser.add_argument("--command", help="Replace the job command.")
    update_schedule = update_parser.add_mutually_exclusive_group(required=False)
    update_schedule.add_argument("--cron", help="Replace the job schedule with a cron expression.")
    update_schedule.add_argument("--every", help="Replace the job schedule with a portable interval.")
    update_parser.add_argument("--description", help="Replace the job description.")
    update_parser.add_argument("--clear-description", action="store_true", help="Remove the job description field.")
    update_parser.add_argument("--working-dir", help="Replace the job-specific working directory.")
    update_parser.add_argument("--clear-working-dir", action="store_true", help="Remove the job-specific working_dir field.")
    update_parser.add_argument("--shell", help="Replace the job-specific shell.")
    update_parser.add_argument("--clear-shell", action="store_true", help="Remove the job-specific shell field.")
    update_parser.add_argument("--overlap", choices=("allow", "forbid"), help="Replace the overlap policy.")
    update_parser.add_argument("--env", action="append", default=[], metavar="KEY=VALUE", help="Replace env with the provided assignments. Repeatable.")
    update_parser.add_argument("--clear-env", action="store_true", help="Remove the job-specific env mapping.")
    add_fields_argument(update_parser)
    update_parser.set_defaults(handler=handle_update)


def handle_list(args: argparse.Namespace) -> int:
    result = list_jobs(
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
    )
    if not result.valid:
        return _print_job_action_error(result)

    payload = {
        "manifest": result.manifest_path,
        "count": f"{len(result.jobs)} of {len(result.jobs)}",
        "jobs": [
            {
                "job_id": job.job_id,
                "enabled": job.enabled,
                "schedule": f"{job.schedule.kind.value}={job.schedule.value}",
                "command": job.execution.command,
            }
            for job in result.jobs
        ],
        "help": [
            "Run `xcron jobs show <job-id>` to inspect one manifest job",
            "Run `xcron apply` to reconcile manifest changes into backend state",
        ],
    }
    print(
        render_toon(
            select_list_fields(
                payload,
                top_level_fields=JOBS_LIST_FIELDS,
                list_key="jobs",
                row_fields=JOBS_LIST_ROW_FIELDS,
                requested_fields=selected_fields(getattr(args, "fields", None)),
            )
        )
    )
    return 0


def handle_show(args: argparse.Namespace) -> int:
    result = show_job(
        args.job_id,
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
    )
    if not result.valid:
        return _print_job_action_error(result)
    if result.job is None:
        return emit_error("job not found in manifest", help_items=("Run `xcron jobs list` to inspect available jobs",))

    payload: dict[str, object] = {
        "manifest": result.manifest_path,
        "job": result.job.qualified_id,
        "enabled": result.job.enabled,
        "schedule": f"{result.job.schedule.kind.value}={result.job.schedule.value}",
        "command": result.job.execution.command,
        "working_dir": result.job.execution.working_dir,
        "shell": result.job.execution.shell,
        "overlap": result.job.execution.overlap.value,
        "help": ["Run `xcron inspect <job-id>` for backend-side detail"],
    }
    if result.job.description:
        payload["description"] = result.job.description
    if result.job.execution.env:
        payload["env"] = [f"{key}={value}" for key, value in result.job.execution.env]
    return emit_payload(
        payload,
        allowed_fields=JOB_SHOW_FIELDS,
        requested_fields=selected_fields(getattr(args, "fields", None)),
    )


def handle_add(args: argparse.Namespace) -> int:
    try:
        payload = _build_add_job_payload(args)
    except ValueError as exc:
        return _print_jobs_cli_error(str(exc))

    result = add_job(
        payload,
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
    )
    if not result.valid:
        return _print_job_action_error(result)
    return _emit_job_mutation_payload(
        "jobs.add",
        result,
        requested_fields=selected_fields(getattr(args, "fields", None)),
        changed_outcome="added",
    )


def handle_remove(args: argparse.Namespace) -> int:
    result = remove_job(
        args.job_id,
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
    )
    if not result.valid:
        return _print_job_action_error(result)
    return _emit_job_mutation_payload(
        "jobs.remove",
        result,
        requested_fields=selected_fields(getattr(args, "fields", None)),
        changed_outcome="removed",
    )


def handle_enable(args: argparse.Namespace) -> int:
    result = enable_job(
        args.job_id,
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
    )
    if not result.valid:
        return _print_job_action_error(result)
    return _emit_job_mutation_payload(
        "jobs.enable",
        result,
        requested_fields=selected_fields(getattr(args, "fields", None)),
        changed_outcome="enabled",
    )


def handle_disable(args: argparse.Namespace) -> int:
    result = disable_job(
        args.job_id,
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
    )
    if not result.valid:
        return _print_job_action_error(result)
    return _emit_job_mutation_payload(
        "jobs.disable",
        result,
        requested_fields=selected_fields(getattr(args, "fields", None)),
        changed_outcome="disabled",
    )


def handle_update(args: argparse.Namespace) -> int:
    try:
        updates, clear_fields = _build_update_payload(args)
    except ValueError as exc:
        return _print_jobs_cli_error(str(exc))
    if not updates and not clear_fields:
        return _print_jobs_cli_error("at least one update field or clear flag is required")

    result = update_job(
        args.job_id,
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
        updates=updates,
        clear_fields=clear_fields,
    )
    if not result.valid:
        return _print_job_action_error(result)
    return _emit_job_mutation_payload(
        "jobs.update",
        result,
        requested_fields=selected_fields(getattr(args, "fields", None)),
        changed_outcome="updated",
    )


def _build_add_job_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": args.job_id,
        "command": args.command,
        "schedule": {"cron": args.cron} if args.cron else {"every": args.every},
        "enabled": not args.disabled,
    }
    if args.description is not None:
        payload["description"] = args.description
    if args.working_dir is not None:
        payload["working_dir"] = args.working_dir
    if args.shell is not None:
        payload["shell"] = args.shell
    if args.overlap is not None:
        payload["overlap"] = args.overlap
    env = _parse_env_assignments(args.env)
    if env:
        payload["env"] = env
    return payload


def _build_update_payload(args: argparse.Namespace) -> tuple[dict[str, Any], tuple[str, ...]]:
    updates: dict[str, Any] = {}
    clear_fields: list[str] = []
    if args.command is not None:
        updates["command"] = args.command
    if args.cron is not None:
        updates["schedule"] = {"cron": args.cron}
    elif args.every is not None:
        updates["schedule"] = {"every": args.every}
    if args.description is not None:
        updates["description"] = args.description
    if args.clear_description:
        clear_fields.append("description")
    if args.working_dir is not None:
        updates["working_dir"] = args.working_dir
    if args.clear_working_dir:
        clear_fields.append("working_dir")
    if args.shell is not None:
        updates["shell"] = args.shell
    if args.clear_shell:
        clear_fields.append("shell")
    if args.overlap is not None:
        updates["overlap"] = args.overlap
    if args.env:
        updates["env"] = _parse_env_assignments(args.env)
    if args.clear_env:
        clear_fields.append("env")
    return updates, tuple(clear_fields)


def _parse_env_assignments(values: Sequence[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for value in values:
        key, sep, remainder = value.partition("=")
        if not sep or not key:
            raise ValueError(f"invalid env assignment, expected KEY=VALUE: {value}")
        env[key] = remainder
    return env


def _print_job_action_error(result: Any) -> int:
    validation = getattr(result, "validation", None)
    details: list[dict[str, str]] = []
    if validation is not None:
        details.extend(validation_details(validation.errors + validation.warnings))
    warnings = getattr(result, "warnings", ())
    if warnings:
        details.extend(validation_details(warnings))
    return emit_error(
        getattr(result, "error", None) or "job action failed",
        details=details,
        help_items=("Run `xcron jobs --help` to review available manifest job commands",),
    )


def _print_jobs_cli_error(message: str) -> int:
    """Print a deterministic CLI-shell error message."""
    return emit_error(
        message,
        code="usage_error",
        exit_code=2,
        help_items=("Run `xcron jobs add --help` or `xcron jobs update --help` to review command usage",),
    )


def _emit_job_mutation_payload(
    kind: str,
    result: Any,
    *,
    requested_fields: Sequence[str],
    changed_outcome: str,
) -> int:
    """Render one AXI mutation payload for jobs commands."""

    target = None
    if getattr(result, "job", None) is not None:
        target = result.job.qualified_id
    elif getattr(result, "removed_job_identifier", None) is not None:
        target = result.removed_job_identifier

    payload = {
        "kind": kind,
        "target": target,
        "outcome": changed_outcome if getattr(result, "changed", True) else "noop",
        "manifest": result.manifest_path,
        "help": [
            "Run `xcron jobs show <job-id>` to inspect the manifest-side result",
            "Run `xcron apply` to reconcile backend state after manifest edits",
        ],
    }
    return emit_payload(
        payload,
        allowed_fields=JOB_MUTATION_FIELDS,
        requested_fields=requested_fields,
    )

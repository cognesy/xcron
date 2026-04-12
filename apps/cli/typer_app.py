"""Parallel Typer shell for xcron migration work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, NoReturn, Optional

import typer

from apps.cli.common import (
    env_flag,
    env_path,
    env_string,
    resolve_project_path,
    validation_details,
)
from apps.cli.output import Output
from libs.actions import (
    add_job,
    apply_project,
    clear_logs,
    disable_job,
    enable_job,
    inspect_job,
    list_jobs,
    list_logs,
    plan_project,
    prune_project,
    remove_job,
    show_job,
    status_project,
    update_job,
    validate_project,
)
from libs.services import (
    capture_session_end,
    collapse_home_path,
    ensure_agent_hooks,
    HookInstallResponse,
    HookSessionEndResponse,
    HookStatusResponse,
    CodexHookStatusResponse,
    ClaudeHookStatusResponse,
    load_help_body,
    map_apply_response,
    map_home_response,
    map_inspect_response,
    map_jobs_list_response,
    map_jobs_mutation_response,
    map_jobs_show_response,
    map_logs_clear_response,
    map_logs_list_response,
    map_plan_response,
    map_prune_response,
    map_status_response,
    map_validation_response,
    inspect_agent_hooks,
    render_toon,
    resolve_xcron_executable,
)


app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=False,
    help=load_help_body("root"),
    rich_markup_mode="markdown",
)
jobs_app = typer.Typer(
    help=load_help_body("jobs/index"),
    short_help="Inspect and edit jobs inside one schedule manifest.",
    rich_markup_mode="markdown",
)
logs_app = typer.Typer(
    help="Inspect and manage wrapper log files for one project.",
    short_help="Inspect and manage wrapper log files.",
    rich_markup_mode="markdown",
)
hooks_app = typer.Typer(help="Manage repo-local Codex and Claude hook integration.", rich_markup_mode="markdown")


def _shared_option(ctx: typer.Context, key: str, value):
    if value is not None:
        return value
    cursor = ctx.parent
    while cursor is not None:
        if key in cursor.params:
            return cursor.params.get(key)
        cursor = cursor.parent
    return value


def _build_output(ctx: typer.Context, contract_name: str, output_format: str | None) -> Output:
    try:
        return Output(ctx, contract_name, output_format)
    except ValueError as exc:
        effective_output = output_format if output_format is not None else _shared_option(ctx, "output_format", None)
        effective_lower = str(effective_output).strip().lower()
        fallback_format = effective_lower if effective_lower in ("json", "tmux") else "toon"
        _emit_bootstrap_usage_error(str(exc), output_format=fallback_format)


def _emit_bootstrap_usage_error(message: str, *, output_format: str) -> NoReturn:
    from libs.services import render_tmux

    payload = {
        "kind": "error",
        "code": "usage_error",
        "message": message,
    }
    if output_format == "json":
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
    elif output_format == "tmux":
        typer.echo(render_tmux(payload))
    else:
        typer.echo(render_toon(payload))
    raise typer.Exit(code=2)


@app.callback()
def main_callback(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    full: bool = typer.Option(False, help="Show full response content instead of truncated previews."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    out = _build_output(ctx, "home", output_format)
    result = plan_project(
        resolve_project_path(project),
        schedule_name=schedule,
        backend=backend,
        state_root=env_path("XCRON_STATE_ROOT"),
    )
    if not result.valid or result.plan is None or result.validation.normalized_manifest is None:
        out.error(
            "project home view unavailable because validation failed",
            details=validation_details(result.validation.errors + result.validation.warnings),
            hints=list(out.contract.default_hints),
        )

    try:
        executable = str(resolve_xcron_executable())
    except RuntimeError:
        executable = "xcron"

    out.print(
        map_home_response(
            result,
            executable=executable,
            contract=out.contract,
            include_plan_changes=out.full,
        )
    )


def _parse_env_assignments(values: List[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for value in values:
        key, sep, remainder = value.partition("=")
        if not sep or not key:
            raise ValueError(f"invalid env assignment, expected KEY=VALUE: {value}")
        env[key] = remainder
    return env


@app.command("validate")
def validate_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    out = _build_output(ctx, "validate", output_format)
    result = validate_project(resolve_project_path(project), schedule_name=schedule)
    if not result.valid or result.hashes is None or result.normalized_manifest is None:
        out.error(
            "project validation failed",
            details=validation_details(result.errors + result.warnings),
            hints=list(out.contract.default_hints),
        )

    out.print(map_validation_response(result))


validate_command.__doc__ = load_help_body("validate")


@app.command("plan")
def plan_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    out = _build_output(ctx, "plan", output_format)
    result = plan_project(
        resolve_project_path(project),
        schedule_name=schedule,
        backend=backend,
        state_root=env_path("XCRON_STATE_ROOT"),
    )
    if not result.valid:
        out.error(
            "project planning failed",
            details=validation_details(result.validation.errors + result.validation.warnings),
            hints=list(out.contract.default_hints),
        )

    out.print(map_plan_response(result, contract=out.contract))


plan_command.__doc__ = load_help_body("plan")


@app.command("status")
def status_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    out = _build_output(ctx, "status", output_format)
    result = status_project(
        resolve_project_path(project),
        schedule_name=schedule,
        backend=backend,
        launch_agents_dir=env_path("XCRON_LAUNCH_AGENTS_DIR"),
        launchctl_domain=env_string("XCRON_LAUNCHCTL_DOMAIN"),
        crontab_path=env_path("XCRON_CRONTAB_PATH"),
    )
    if not result.valid or result.plan is None:
        out.error(
            "project status inspection failed",
            details=validation_details(result.validation.errors + result.validation.warnings),
            hints=list(out.contract.default_hints),
        )

    out.print(map_status_response(result, contract=out.contract))


status_command.__doc__ = load_help_body("status")


@app.command("inspect")
def inspect_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., help="Project-local or qualified job identifier."),
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    full: bool = typer.Option(False, help="Show full response content instead of truncated previews."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    out = _build_output(ctx, "inspect", output_format)
    result = inspect_job(
        job_id,
        resolve_project_path(project),
        schedule_name=schedule,
        backend=backend,
        launch_agents_dir=env_path("XCRON_LAUNCH_AGENTS_DIR"),
        launchctl_domain=env_string("XCRON_LAUNCHCTL_DOMAIN"),
        crontab_path=env_path("XCRON_CRONTAB_PATH"),
    )
    if not result.valid:
        details = validation_details(result.status.validation.errors + result.status.validation.warnings)
        if result.error and not details:
            details = [{"field": "job_id", "issue": result.error}]
        out.error(result.error or "job inspection failed", details=details, hints=list(out.contract.default_hints))

    out.print(map_inspect_response(result, contract=out.contract, job_id=job_id, full=out.full))


inspect_command.__doc__ = load_help_body("inspect")


@app.command("apply")
def apply_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    out = _build_output(ctx, "apply", output_format)
    result = apply_project(
        resolve_project_path(project),
        schedule_name=schedule,
        backend=backend,
        state_root=env_path("XCRON_STATE_ROOT"),
        launch_agents_dir=env_path("XCRON_LAUNCH_AGENTS_DIR"),
        launchctl_domain=env_string("XCRON_LAUNCHCTL_DOMAIN"),
        crontab_path=env_path("XCRON_CRONTAB_PATH"),
        manage_launchctl=env_flag("XCRON_MANAGE_LAUNCHCTL", default=True),
        manage_crontab=env_flag("XCRON_MANAGE_CRONTAB", default=True),
    )
    if not result.valid:
        out.error(
            "project apply failed",
            details=validation_details(result.plan_result.validation.errors + result.plan_result.validation.warnings),
            hints=list(out.contract.default_hints),
        )

    out.print(map_apply_response(result, contract=out.contract))


apply_command.__doc__ = load_help_body("apply")


@app.command("prune")
def prune_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    out = _build_output(ctx, "prune", output_format)
    result = prune_project(
        resolve_project_path(project),
        schedule_name=schedule,
        backend=backend,
        state_root=env_path("XCRON_STATE_ROOT"),
        launch_agents_dir=env_path("XCRON_LAUNCH_AGENTS_DIR"),
        launchctl_domain=env_string("XCRON_LAUNCHCTL_DOMAIN"),
        crontab_path=env_path("XCRON_CRONTAB_PATH"),
        manage_launchctl=env_flag("XCRON_MANAGE_LAUNCHCTL", default=True),
        manage_crontab=env_flag("XCRON_MANAGE_CRONTAB", default=True),
    )
    if not result.valid:
        out.error(result.error or "project prune failed", hints=list(out.contract.default_hints))

    out.print(map_prune_response(result, contract=out.contract))


prune_command.__doc__ = load_help_body("prune")


@jobs_app.command("list")
def jobs_list_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    out = _build_output(ctx, "jobs.list", output_format)
    result = list_jobs(resolve_project_path(project), schedule_name=schedule)
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        if result.warnings:
            details.extend(validation_details(result.warnings))
        out.error(result.error or "job action failed", details=details, hints=list(out.contract.default_hints))

    out.print(map_jobs_list_response(result, contract=out.contract))


jobs_list_command.__doc__ = load_help_body("jobs/list")


@jobs_app.command("show")
def jobs_show_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., help="Project-local or qualified job identifier."),
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    out = _build_output(ctx, "jobs.show", output_format)
    result = show_job(job_id, resolve_project_path(project), schedule_name=schedule)
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        if result.warnings:
            details.extend(validation_details(result.warnings))
        out.error(result.error or "job action failed", details=details, hints=list(out.contract.default_hints))
    if result.job is None:
        out.error("job not found in manifest", hints=["Run `xcron jobs list` to inspect available jobs"])

    out.print(map_jobs_show_response(result, contract=out.contract))


jobs_show_command.__doc__ = load_help_body("jobs/show")


@jobs_app.command("add")
def jobs_add_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., help="Project-local job identifier to add."),
    command: str = typer.Option(..., help="Shell command for the new job."),
    cron: Optional[str] = typer.Option(None, help="Cron expression for the new job."),
    every: Optional[str] = typer.Option(None, help="Portable interval string such as 15m or 1h."),
    description: Optional[str] = typer.Option(None, help="Optional human description."),
    working_dir: Optional[str] = typer.Option(None, help="Optional job-specific working directory."),
    shell: Optional[str] = typer.Option(None, help="Optional job-specific shell."),
    overlap: Optional[str] = typer.Option(None, help="Optional overlap policy override."),
    env: List[str] = typer.Option([], help="Environment variable assignment. Repeatable."),
    disabled: bool = typer.Option(False, help="Create the job as disabled in YAML."),
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    out = _build_output(ctx, "jobs.add", output_format)
    if bool(cron) == bool(every):
        out.error("exactly one of --cron or --every is required", code="usage_error", exit_code=2)
    try:
        payload = {
            "id": job_id,
            "command": command,
            "schedule": {"cron": cron} if cron else {"every": every},
            "enabled": not disabled,
        }
        if description is not None:
            payload["description"] = description
        if working_dir is not None:
            payload["working_dir"] = working_dir
        if shell is not None:
            payload["shell"] = shell
        if overlap is not None:
            payload["overlap"] = overlap
        parsed_env = _parse_env_assignments(env)
        if parsed_env:
            payload["env"] = parsed_env
    except ValueError as exc:
        out.error(str(exc), code="usage_error", exit_code=2)
    result = add_job(payload, resolve_project_path(project), schedule_name=schedule)
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        if result.warnings:
            details.extend(validation_details(result.warnings))
        out.error(result.error or "job action failed", details=details, hints=list(out.contract.default_hints))

    out.print(map_jobs_mutation_response(result, contract=out.contract, changed_outcome="added"))


jobs_add_command.__doc__ = load_help_body("jobs/add")


def _run_jobs_mutation(
    ctx: typer.Context,
    contract_name: str,
    changed_outcome: str,
    fn,
    *,
    job_id: str,
    project: Optional[str],
    schedule: Optional[str],
    output_format: str | None,
) -> None:
    out = _build_output(ctx, contract_name, output_format)
    result = fn(job_id, resolve_project_path(project), schedule_name=schedule)
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        if result.warnings:
            details.extend(validation_details(result.warnings))
        out.error(result.error or "job action failed", details=details, hints=list(out.contract.default_hints))

    out.print(map_jobs_mutation_response(result, contract=out.contract, changed_outcome=changed_outcome))


@jobs_app.command("remove")
def jobs_remove_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(...),
    project: Optional[str] = typer.Option(None),
    schedule: Optional[str] = typer.Option(None),
    fields: Optional[str] = typer.Option(None),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    _run_jobs_mutation(ctx, "jobs.remove", "removed", remove_job, job_id=job_id, project=project, schedule=schedule, output_format=output_format)


jobs_remove_command.__doc__ = load_help_body("jobs/remove")


@jobs_app.command("enable")
def jobs_enable_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(...),
    project: Optional[str] = typer.Option(None),
    schedule: Optional[str] = typer.Option(None),
    fields: Optional[str] = typer.Option(None),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    _run_jobs_mutation(ctx, "jobs.enable", "enabled", enable_job, job_id=job_id, project=project, schedule=schedule, output_format=output_format)


jobs_enable_command.__doc__ = load_help_body("jobs/enable")


@jobs_app.command("disable")
def jobs_disable_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(...),
    project: Optional[str] = typer.Option(None),
    schedule: Optional[str] = typer.Option(None),
    fields: Optional[str] = typer.Option(None),
    output_format: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    _run_jobs_mutation(ctx, "jobs.disable", "disabled", disable_job, job_id=job_id, project=project, schedule=schedule, output_format=output_format)


jobs_disable_command.__doc__ = load_help_body("jobs/disable")


@jobs_app.command("update")
def jobs_update_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(...),
    command: Optional[str] = typer.Option(None),
    cron: Optional[str] = typer.Option(None),
    every: Optional[str] = typer.Option(None),
    description: Optional[str] = typer.Option(None),
    clear_description: bool = typer.Option(False),
    working_dir: Optional[str] = typer.Option(None),
    clear_working_dir: bool = typer.Option(False),
    shell: Optional[str] = typer.Option(None),
    clear_shell: bool = typer.Option(False),
    overlap: Optional[str] = typer.Option(None),
    env: List[str] = typer.Option([]),
    clear_env: bool = typer.Option(False),
    project: Optional[str] = typer.Option(None),
    schedule: Optional[str] = typer.Option(None),
    fields: Optional[str] = typer.Option(None),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json or toon. Defaults to toon."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    out = _build_output(ctx, "jobs.update", output_format)
    updates: dict[str, object] = {}
    clear_fields: list[str] = []
    if command is not None:
        updates["command"] = command
    if cron is not None:
        updates["schedule"] = {"cron": cron}
    elif every is not None:
        updates["schedule"] = {"every": every}
    if description is not None:
        updates["description"] = description
    if clear_description:
        clear_fields.append("description")
    if working_dir is not None:
        updates["working_dir"] = working_dir
    if clear_working_dir:
        clear_fields.append("working_dir")
    if shell is not None:
        updates["shell"] = shell
    if clear_shell:
        clear_fields.append("shell")
    if overlap is not None:
        updates["overlap"] = overlap
    if env:
        updates["env"] = _parse_env_assignments(env)
    if clear_env:
        clear_fields.append("env")
    if not updates and not clear_fields:
        out.error("at least one update field or clear flag is required", code="usage_error", exit_code=2)

    result = update_job(
        job_id,
        resolve_project_path(project),
        schedule_name=schedule,
        updates=updates,
        clear_fields=tuple(clear_fields),
    )
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        if result.warnings:
            details.extend(validation_details(result.warnings))
        out.error(result.error or "job action failed", details=details, hints=list(out.contract.default_hints))

    out.print(map_jobs_mutation_response(result, contract=out.contract, changed_outcome="updated"))


jobs_update_command.__doc__ = load_help_body("jobs/update")


@logs_app.command("list")
def logs_list_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    job: Optional[str] = typer.Option(None, help="Filter to one job by project-local or qualified identifier."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json, toon, or tmux. Defaults to toon."),
) -> None:
    """List wrapper log files for one project."""
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    out = _build_output(ctx, "logs.list", output_format)
    result = list_logs(
        resolve_project_path(project),
        schedule_name=schedule,
        job_filter=job,
        state_root=env_path("XCRON_STATE_ROOT"),
    )
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        out.error(result.error or "log listing failed", details=details, hints=list(out.contract.default_hints))

    out.print(map_logs_list_response(result, contract=out.contract))


@logs_app.command("clear")
def logs_clear_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    job: Optional[str] = typer.Option(None, help="Filter to one job by project-local or qualified identifier."),
    apply: bool = typer.Option(False, "--apply", help="Actually truncate log files. Without this flag, runs in dry-run mode."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    output_format: Optional[str] = typer.Option(None, "--output", "-o", help="Render command output as json, toon, or tmux. Defaults to toon."),
) -> None:
    """Clear (truncate) wrapper log files for one project. Dry-run by default."""
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    out = _build_output(ctx, "logs.clear", output_format)
    result = clear_logs(
        resolve_project_path(project),
        schedule_name=schedule,
        job_filter=job,
        state_root=env_path("XCRON_STATE_ROOT"),
        dry_run=not apply,
    )
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        out.error(result.error or "log clear failed", details=details, hints=list(out.contract.default_hints))

    out.print(map_logs_clear_response(result, contract=out.contract))


@hooks_app.command("install")
def hooks_install_command(ctx: typer.Context, output_format: Optional[str] = typer.Option(None, "--output", "-o")) -> None:
    out = _build_output(ctx, "hooks.install", output_format)
    result = ensure_agent_hooks(Path.cwd())
    out.print(HookInstallResponse(kind="hooks.install", changed=len(result.changed_files), files=result.changed_files))


@hooks_app.command("status")
def hooks_status_command(ctx: typer.Context, output_format: Optional[str] = typer.Option(None, "--output", "-o")) -> None:
    out = _build_output(ctx, "hooks.status", output_format)
    result = inspect_agent_hooks(Path.cwd())
    out.print(
        HookStatusResponse(
            kind="hooks.status",
            executable=result.executable_path,
            codex=CodexHookStatusResponse(
                config_path=result.codex.config_path,
                hooks_path=result.codex.hooks_path,
                config_exists=result.codex.config_exists,
                hooks_exists=result.codex.hooks_exists,
                feature_enabled=result.codex.feature_enabled,
                session_start_matches=result.codex.session_start_matches,
                session_end_matches=result.codex.session_end_matches,
            ),
            claude=ClaudeHookStatusResponse(
                settings_path=result.claude.settings_path,
                settings_exists=result.claude.settings_exists,
                session_start_matches=result.claude.session_start_matches,
                stop_matches=result.claude.stop_matches,
            ),
        )
    )


@hooks_app.command("repair")
def hooks_repair_command(ctx: typer.Context, output_format: Optional[str] = typer.Option(None, "--output", "-o")) -> None:
    hooks_install_command(ctx, output_format)


@hooks_app.command("session-start", hidden=True)
def hooks_session_start_command(ctx: typer.Context, output_format: Optional[str] = typer.Option(None, "--output", "-o")) -> None:
    out = _build_output(ctx, "hooks.session-start", output_format)
    result = plan_project(Path.cwd(), state_root=None)
    if not result.valid or result.plan is None or result.validation.normalized_manifest is None:
        out.error("session-start context unavailable", hints=["Run `xcron validate` in this project"])

    out.print(
        map_home_response(
            result,
            executable=str(resolve_xcron_executable()),
            contract=out.contract,
            include_plan_changes=False,
        )
    )


@hooks_app.command("session-end", hidden=True)
def hooks_session_end_command(ctx: typer.Context, output_format: Optional[str] = typer.Option(None, "--output", "-o")) -> None:
    out = _build_output(ctx, "hooks.session-end", output_format)
    log_path = capture_session_end(Path.cwd())
    out.print(HookSessionEndResponse(kind="hooks.session_end", log=str(log_path)))


app.add_typer(jobs_app, name="jobs")
app.add_typer(logs_app, name="logs")
app.add_typer(hooks_app, name="hooks")


def run() -> None:
    app()

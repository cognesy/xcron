"""Parallel Typer shell for xcron migration work."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from apps.cli.common import env_flag, env_path, env_string, resolve_project_path, selected_contract_fields, validation_details
from libs.actions import (
    add_job,
    apply_project,
    disable_job,
    enable_job,
    inspect_job,
    list_jobs,
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
    get_command_contract,
    load_help_body,
    map_error_response,
    map_apply_response,
    map_home_response,
    map_inspect_response,
    map_jobs_list_response,
    map_jobs_mutation_response,
    map_jobs_show_response,
    map_plan_response,
    map_prune_response,
    map_status_response,
    map_validation_response,
    inspect_agent_hooks,
    render_collection_response_toon,
    render_list_response_toon,
    render_nested_response_toon,
    render_response_toon,
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
hooks_app = typer.Typer(help="Manage repo-local Codex and Claude hook integration.", rich_markup_mode="markdown")
def _emit_output(text: str) -> None:
    typer.echo(text)


def _emit_error(message: str, *, details: list[dict[str, str]] | None = None, help_items: tuple[str, ...] = (), code: str = "runtime_error", exit_code: int = 1) -> None:
    _emit_output(
        render_toon(
            map_error_response(
                message,
                code=code,
                details=details or (),
                help_items=help_items,
            ).to_payload()
        )
    )
    raise typer.Exit(code=exit_code)


def _shared_option(ctx: typer.Context, key: str, value):
    if value is not None:
        return value
    cursor = ctx.parent
    while cursor is not None:
        if key in cursor.params:
            return cursor.params.get(key)
        cursor = cursor.parent
    return value


@app.callback()
def main_callback(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
    full: bool = typer.Option(False, help="Show full response content instead of truncated previews."),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    contract = get_command_contract("home")
    result = plan_project(
        resolve_project_path(project),
        schedule_name=schedule,
        backend=backend,
        state_root=env_path("XCRON_STATE_ROOT"),
    )
    if not result.valid or result.plan is None or result.validation.normalized_manifest is None:
        _emit_error(
            "project home view unavailable because validation failed",
            details=validation_details(result.validation.errors + result.validation.warnings),
            help_items=contract.default_hints,
        )
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)

    try:
        executable = str(resolve_xcron_executable())
    except RuntimeError:
        executable = "xcron"

    _emit_output(
        render_collection_response_toon(
            map_home_response(
                result,
                executable=executable,
                contract=contract,
                include_plan_changes=full,
            ).to_payload(),
            allowed_fields=contract.allowed_fields,
            collection_fields=contract.collection_fields,
            requested_fields=requested_fields,
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
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    fields = _shared_option(ctx, "fields", fields)
    contract = get_command_contract("validate")
    result = validate_project(resolve_project_path(project), schedule_name=schedule)
    if not result.valid or result.hashes is None or result.normalized_manifest is None:
        _emit_error(
            "project validation failed",
            details=validation_details(result.errors + result.warnings),
            help_items=contract.default_hints,
        )
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)

    _emit_output(
        render_response_toon(
            map_validation_response(result).to_payload(),
            allowed_fields=contract.allowed_fields,
            requested_fields=requested_fields,
        )
    )


validate_command.__doc__ = load_help_body("validate")


@app.command("plan")
def plan_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    fields = _shared_option(ctx, "fields", fields)
    contract = get_command_contract("plan")
    result = plan_project(
        resolve_project_path(project),
        schedule_name=schedule,
        backend=backend,
        state_root=env_path("XCRON_STATE_ROOT"),
    )
    if not result.valid:
        _emit_error(
            "project planning failed",
            details=validation_details(result.validation.errors + result.validation.warnings),
            help_items=contract.default_hints,
        )
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)

    _emit_output(
        render_list_response_toon(
            map_plan_response(result, contract=contract).to_payload(),
            allowed_fields=contract.allowed_fields,
            list_key=contract.list_key or "changes",
            row_fields=contract.list_row_fields,
            requested_fields=requested_fields,
        )
    )


plan_command.__doc__ = load_help_body("plan")


@app.command("status")
def status_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    fields = _shared_option(ctx, "fields", fields)
    contract = get_command_contract("status")
    result = status_project(
        resolve_project_path(project),
        schedule_name=schedule,
        backend=backend,
        launch_agents_dir=env_path("XCRON_LAUNCH_AGENTS_DIR"),
        launchctl_domain=env_string("XCRON_LAUNCHCTL_DOMAIN"),
        crontab_path=env_path("XCRON_CRONTAB_PATH"),
    )
    if not result.valid or result.plan is None:
        _emit_error(
            "project status inspection failed",
            details=validation_details(result.validation.errors + result.validation.warnings),
            help_items=contract.default_hints,
        )
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)

    _emit_output(
        render_list_response_toon(
            map_status_response(result, contract=contract).to_payload(),
            allowed_fields=contract.allowed_fields,
            list_key=contract.list_key or "statuses",
            row_fields=contract.list_row_fields,
            requested_fields=requested_fields,
        )
    )


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
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    fields = _shared_option(ctx, "fields", fields)
    full = _shared_option(ctx, "full", full)
    contract = get_command_contract("inspect")
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
        _emit_error(result.error or "job inspection failed", details=details, help_items=contract.default_hints)
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)

    _emit_output(
        render_nested_response_toon(
            map_inspect_response(result, contract=contract, job_id=job_id, full=full).to_payload(),
            allowed_fields=contract.allowed_fields,
            nested_fields=contract.nested_fields,
            requested_fields=requested_fields,
        )
    )


inspect_command.__doc__ = load_help_body("inspect")


@app.command("apply")
def apply_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    fields = _shared_option(ctx, "fields", fields)
    contract = get_command_contract("apply")
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
        _emit_error(
            "project apply failed",
            details=validation_details(result.plan_result.validation.errors + result.plan_result.validation.warnings),
            help_items=contract.default_hints,
        )
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)

    _emit_output(
        render_response_toon(
            map_apply_response(result, contract=contract).to_payload(),
            allowed_fields=contract.allowed_fields,
            requested_fields=requested_fields,
        )
    )


apply_command.__doc__ = load_help_body("apply")


@app.command("prune")
def prune_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    backend: Optional[str] = typer.Option(None, help="Override the backend instead of using the platform default."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    backend = _shared_option(ctx, "backend", backend)
    fields = _shared_option(ctx, "fields", fields)
    contract = get_command_contract("prune")
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
        _emit_error(result.error or "project prune failed", help_items=contract.default_hints)
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)

    _emit_output(
        render_response_toon(
            map_prune_response(result, contract=contract).to_payload(),
            allowed_fields=contract.allowed_fields,
            requested_fields=requested_fields,
        )
    )


prune_command.__doc__ = load_help_body("prune")


@jobs_app.command("list")
def jobs_list_command(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    fields = _shared_option(ctx, "fields", fields)
    contract = get_command_contract("jobs.list")
    result = list_jobs(resolve_project_path(project), schedule_name=schedule)
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        if result.warnings:
            details.extend(validation_details(result.warnings))
        _emit_error(result.error or "job action failed", details=details, help_items=contract.default_hints)
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)

    _emit_output(
        render_list_response_toon(
            map_jobs_list_response(result, contract=contract).to_payload(),
            allowed_fields=contract.allowed_fields,
            list_key=contract.list_key or "jobs",
            row_fields=contract.list_row_fields,
            requested_fields=requested_fields,
        )
    )


jobs_list_command.__doc__ = load_help_body("jobs/list")


@jobs_app.command("show")
def jobs_show_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., help="Project-local or qualified job identifier."),
    project: Optional[str] = typer.Option(None, help="Path to the project root containing resources/schedules/."),
    schedule: Optional[str] = typer.Option(None, help="Schedule name under resources/schedules/."),
    fields: Optional[str] = typer.Option(None, help="Comma-separated list of response fields to include."),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    fields = _shared_option(ctx, "fields", fields)
    contract = get_command_contract("jobs.show")
    result = show_job(job_id, resolve_project_path(project), schedule_name=schedule)
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        if result.warnings:
            details.extend(validation_details(result.warnings))
        _emit_error(result.error or "job action failed", details=details, help_items=contract.default_hints)
    if result.job is None:
        _emit_error("job not found in manifest", help_items=("Run `xcron jobs list` to inspect available jobs",))
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)
    _emit_output(
        render_response_toon(
            map_jobs_show_response(result, contract=contract).to_payload(),
            allowed_fields=contract.allowed_fields,
            requested_fields=requested_fields,
        )
    )


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
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    fields = _shared_option(ctx, "fields", fields)
    if bool(cron) == bool(every):
        _emit_error("exactly one of --cron or --every is required", code="usage_error", exit_code=2)
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
        _emit_error(str(exc), code="usage_error", exit_code=2)
    contract = get_command_contract("jobs.add")
    result = add_job(payload, resolve_project_path(project), schedule_name=schedule)
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        if result.warnings:
            details.extend(validation_details(result.warnings))
        _emit_error(result.error or "job action failed", details=details, help_items=contract.default_hints)
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)
    _emit_output(
        render_response_toon(
            map_jobs_mutation_response(result, contract=contract, changed_outcome="added").to_payload(),
            allowed_fields=contract.allowed_fields,
            requested_fields=requested_fields,
        )
    )


jobs_add_command.__doc__ = load_help_body("jobs/add")


def _run_jobs_mutation(
    contract_name: str,
    changed_outcome: str,
    fn,
    *,
    job_id: str,
    project: Optional[str],
    schedule: Optional[str],
    fields: Optional[str],
) -> None:
    contract = get_command_contract(contract_name)
    result = fn(job_id, resolve_project_path(project), schedule_name=schedule)
    if not result.valid:
        details = []
        if result.validation is not None:
            details.extend(validation_details(result.validation.errors + result.validation.warnings))
        if result.warnings:
            details.extend(validation_details(result.warnings))
        _emit_error(result.error or "job action failed", details=details, help_items=contract.default_hints)
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)
    _emit_output(
        render_response_toon(
            map_jobs_mutation_response(result, contract=contract, changed_outcome=changed_outcome).to_payload(),
            allowed_fields=contract.allowed_fields,
            requested_fields=requested_fields,
        )
    )


@jobs_app.command("remove")
def jobs_remove_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(...),
    project: Optional[str] = typer.Option(None),
    schedule: Optional[str] = typer.Option(None),
    fields: Optional[str] = typer.Option(None),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    fields = _shared_option(ctx, "fields", fields)
    _run_jobs_mutation("jobs.remove", "removed", remove_job, job_id=job_id, project=project, schedule=schedule, fields=fields)


jobs_remove_command.__doc__ = load_help_body("jobs/remove")


@jobs_app.command("enable")
def jobs_enable_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(...),
    project: Optional[str] = typer.Option(None),
    schedule: Optional[str] = typer.Option(None),
    fields: Optional[str] = typer.Option(None),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    fields = _shared_option(ctx, "fields", fields)
    _run_jobs_mutation("jobs.enable", "enabled", enable_job, job_id=job_id, project=project, schedule=schedule, fields=fields)


jobs_enable_command.__doc__ = load_help_body("jobs/enable")


@jobs_app.command("disable")
def jobs_disable_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(...),
    project: Optional[str] = typer.Option(None),
    schedule: Optional[str] = typer.Option(None),
    fields: Optional[str] = typer.Option(None),
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    fields = _shared_option(ctx, "fields", fields)
    _run_jobs_mutation("jobs.disable", "disabled", disable_job, job_id=job_id, project=project, schedule=schedule, fields=fields)


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
) -> None:
    project = _shared_option(ctx, "project", project)
    schedule = _shared_option(ctx, "schedule", schedule)
    fields = _shared_option(ctx, "fields", fields)
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
        _emit_error("at least one update field or clear flag is required", code="usage_error", exit_code=2)

    contract = get_command_contract("jobs.update")
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
        _emit_error(result.error or "job action failed", details=details, help_items=contract.default_hints)
    try:
        requested_fields = selected_contract_fields(contract, fields)
    except ValueError as exc:
        _emit_error(str(exc), help_items=contract.default_hints, code="usage_error", exit_code=2)
    _emit_output(
        render_response_toon(
            map_jobs_mutation_response(result, contract=contract, changed_outcome="updated").to_payload(),
            allowed_fields=contract.allowed_fields,
            requested_fields=requested_fields,
        )
    )


jobs_update_command.__doc__ = load_help_body("jobs/update")


@hooks_app.command("install")
def hooks_install_command() -> None:
    result = ensure_agent_hooks(Path.cwd())
    _emit_output(render_toon({"kind": "hooks.install", "changed": len(result.changed_files), "files": result.changed_files}))


@hooks_app.command("status")
def hooks_status_command() -> None:
    result = inspect_agent_hooks(Path.cwd())
    _emit_output(
        render_toon(
            {
                "kind": "hooks.status",
                "executable": result.executable_path,
                "codex": {
                    "config_path": result.codex.config_path,
                    "hooks_path": result.codex.hooks_path,
                    "config_exists": result.codex.config_exists,
                    "hooks_exists": result.codex.hooks_exists,
                    "feature_enabled": result.codex.feature_enabled,
                    "session_start_matches": result.codex.session_start_matches,
                    "session_end_matches": result.codex.session_end_matches,
                },
                "claude": {
                    "settings_path": result.claude.settings_path,
                    "settings_exists": result.claude.settings_exists,
                    "session_start_matches": result.claude.session_start_matches,
                    "stop_matches": result.claude.stop_matches,
                },
            }
        )
    )


@hooks_app.command("repair")
def hooks_repair_command() -> None:
    hooks_install_command()


@hooks_app.command("session-start", hidden=True)
def hooks_session_start_command() -> None:
    result = plan_project(Path.cwd(), state_root=None)
    if not result.valid or result.plan is None or result.validation.normalized_manifest is None:
        _emit_error("session-start context unavailable", help_items=("Run `xcron validate` in this project",))
    payload = map_home_response(
        result,
        executable=str(resolve_xcron_executable()),
        contract=get_command_contract("hooks.session-start"),
        include_plan_changes=False,
    ).to_payload()
    _emit_output(
        render_collection_response_toon(
            payload,
            allowed_fields=get_command_contract("hooks.session-start").allowed_fields,
            collection_fields=get_command_contract("hooks.session-start").collection_fields,
        )
    )


@hooks_app.command("session-end", hidden=True)
def hooks_session_end_command() -> None:
    log_path = capture_session_end(Path.cwd())
    _emit_output(render_toon({"kind": "hooks.session_end", "log": str(log_path)}))


app.add_typer(jobs_app, name="jobs")
app.add_typer(hooks_app, name="hooks")


def run() -> None:
    app()

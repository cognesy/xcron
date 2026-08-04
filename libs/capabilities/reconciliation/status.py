"""Inspect actual deployed state for one project and compare it to desired state."""

from __future__ import annotations

from pathlib import Path

from xcron_libs.capabilities.reconciliation.contracts import (
    SchedulerRuntimeOptions,
    StatusProjectResult,
)
from xcron_libs.capabilities.reconciliation.registry import (
    SchedulerRegistry,
    default_scheduler_registry,
)
from xcron_libs.capabilities.reconciliation.validation import validate_project
from xcron_libs.capabilities.reconciliation.domain import build_project_plan, build_status_entries
from xcron_libs.capabilities.reconciliation.ports import NullOutcomeRecorder, OutcomeRecorder
from xcron_libs.shared.observability import get_logger, instrument_action
from xcron_libs.capabilities.reconciliation.registry import default_backend_for_current_platform

LOGGER = get_logger(__name__)


@instrument_action("status_project")
def status_project(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    backend: str | None = None,
    platform: str | None = None,
    launch_agents_dir: str | Path | None = None,
    launchctl_domain: str | None = None,
    crontab_path: str | Path | None = None,
    scheduler_registry: SchedulerRegistry | None = None,
    outcome_recorder: OutcomeRecorder | None = None,
) -> StatusProjectResult:
    """Compare desired state to actual backend state for one project."""
    outcomes = outcome_recorder or NullOutcomeRecorder()
    outcomes.record("status.calls")
    validation = validate_project(project_path, schedule_name=schedule_name)
    if not validation.valid or validation.normalized_manifest is None or validation.hashes is None:
        outcomes.record("status.failed")
        LOGGER.warning(
            "status_validation_failed",
            project_root=validation.project_root,
            manifest_path=validation.manifest_path,
            error_count=len(validation.errors),
            warning_count=len(validation.warnings),
        )
        return StatusProjectResult(valid=False, backend=None, validation=validation)

    selected_backend = backend or default_backend_for_current_platform(platform=platform)
    project_id = validation.normalized_manifest.project_id
    options = SchedulerRuntimeOptions.create(
        launch_agents_dir=launch_agents_dir,
        launchctl_domain=launchctl_domain,
        crontab_path=crontab_path,
    )
    scheduler = (scheduler_registry or default_scheduler_registry()).require(selected_backend)
    actual_state = scheduler.collect_project_state(project_id, options=options)
    inspections = scheduler.inspect_project(
        project_id,
        options=options,
        include_native_detail=False,
    )

    plan = build_project_plan(
        validation.normalized_manifest,
        selected_backend,
        validation.hashes.manifest_hash,
        validation.hashes.job_hashes,
        validation.hashes.job_definition_hashes,
        actual_state,
    )
    LOGGER.info(
        "project_status_built",
        project_id=project_id,
        backend=selected_backend,
        change_count=len(plan.changes),
        inspection_count=len(inspections),
        deployed_job_count=len(actual_state.jobs),
    )
    outcomes.record("status.succeeded")
    return StatusProjectResult(
        valid=True,
        backend=selected_backend,
        validation=validation,
        plan=plan,
        statuses=build_status_entries(plan),
        inspections=tuple(inspections),
    )

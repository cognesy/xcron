"""Apply one project's desired schedule state to the selected backend."""

from __future__ import annotations

from pathlib import Path

from xcron_libs.capabilities.reconciliation.contracts import (
    ApplyProjectResult,
    DeploymentPlan,
    PlanProjectResult,
    SchedulerRuntimeOptions,
)
from xcron_libs.capabilities.reconciliation.scheduler_registry import (
    SchedulerRegistry,
    default_scheduler_registry,
)
from xcron_libs.capabilities.reconciliation.status import status_project
from xcron_libs.services.metrics import MetricsService
from xcron_libs.services.observability import get_logger, instrument_action
from xcron_libs.services.state_store import resolve_project_state_path

LOGGER = get_logger(__name__)


@instrument_action("apply_project")
def apply_project(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    backend: str | None = None,
    state_root: str | Path | None = None,
    platform: str | None = None,
    launch_agents_dir: str | Path | None = None,
    launchctl_domain: str | None = None,
    crontab_path: str | Path | None = None,
    manage_launchctl: bool = True,
    manage_crontab: bool = True,
    scheduler_registry: SchedulerRegistry | None = None,
) -> ApplyProjectResult:
    """Apply one project's desired state using the selected backend."""
    metrics = MetricsService()
    metrics.increment("apply.calls")
    registry = scheduler_registry or default_scheduler_registry()
    options = SchedulerRuntimeOptions.create(
        state_root=state_root,
        launch_agents_dir=launch_agents_dir,
        launchctl_domain=launchctl_domain,
        crontab_path=crontab_path,
        manage_launchctl=manage_launchctl,
        manage_crontab=manage_crontab,
    )
    status_result = status_project(
        project_path,
        schedule_name=schedule_name,
        backend=backend,
        platform=platform,
        launch_agents_dir=launch_agents_dir,
        launchctl_domain=launchctl_domain,
        crontab_path=crontab_path,
        scheduler_registry=registry,
    )
    if not status_result.valid or status_result.backend is None or status_result.plan is None:
        metrics.increment("apply.failed")
        LOGGER.warning(
            "apply_status_failed",
            backend=status_result.backend,
            error_count=len(status_result.validation.errors),
            warning_count=len(status_result.validation.warnings),
        )
        plan_result = PlanProjectResult(
            valid=False,
            validation=status_result.validation,
            backend=None,
            state_path=None,
        )
        return ApplyProjectResult(valid=False, backend=None, plan_result=plan_result)

    plan_result = PlanProjectResult(
        valid=True,
        validation=status_result.validation,
        backend=status_result.backend,
        state_path=str(
            resolve_project_state_path(
                status_result.validation.normalized_manifest.project_id,
                state_root=options.state_root,
            )
        ),
        changes=status_result.plan.changes,
        plan=status_result.plan,
    )

    scheduler = registry.require(plan_result.backend)
    if plan_result.plan is not None:
        schedule_errors = scheduler.schedule_errors(plan_result.plan.manifest.jobs)
        if schedule_errors:
            metrics.increment("apply.failed")
            LOGGER.error(
                "apply_backend_incompatible_schedules",
                project_id=plan_result.plan.manifest.project_id,
                backend=plan_result.backend,
                incompatible_jobs=[e.qualified_id for e in schedule_errors],
                reasons=[e.reason for e in schedule_errors],
            )
            return ApplyProjectResult(
                valid=False,
                backend=plan_result.backend,
                plan_result=plan_result,
            )

    if plan_result.plan is None or plan_result.validation.hashes is None:
        raise RuntimeError("valid apply plan unexpectedly missing deployment data")
    deployment = DeploymentPlan(
        backend=plan_result.backend,
        plan=plan_result.plan,
        state_path=plan_result.state_path or "",
        manifest_hash=plan_result.validation.hashes.manifest_hash,
        job_hashes=plan_result.validation.hashes.job_hashes,
        job_definition_hashes=plan_result.validation.hashes.job_definition_hashes,
    )
    applied_state = scheduler.apply(deployment, options=options)

    LOGGER.info(
        "project_applied",
        project_id=status_result.validation.normalized_manifest.project_id,
        backend=plan_result.backend,
        change_count=len(plan_result.changes),
        applied_job_count=len(applied_state.jobs),
        state_path=plan_result.state_path,
    )
    metrics.increment("apply.succeeded")
    metrics.increment("jobs.applied", len(applied_state.jobs))
    return ApplyProjectResult(
        valid=True,
        backend=plan_result.backend,
        plan_result=plan_result,
        applied_state=applied_state,
    )

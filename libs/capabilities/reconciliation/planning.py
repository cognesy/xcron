"""Plan desired-vs-deployed changes for one selected project schedule manifest."""

from __future__ import annotations

from pathlib import Path

from xcron_libs.capabilities.reconciliation.contracts import PlanProjectResult
from xcron_libs.capabilities.reconciliation.validation import validate_project
from xcron_libs.capabilities.reconciliation.cron_policy import (
    cron_incompatible_reason,
    cron_schedule_errors,
)
from xcron_libs.capabilities.reconciliation.registry import (
    SchedulerRegistry,
    default_backend_for_current_platform,
    default_scheduler_registry,
)
from xcron_libs.capabilities.reconciliation.domain import PlanChange, PlanChangeKind, ProjectPlan, build_project_plan
from xcron_libs.domain.models import NormalizedJob
from xcron_libs.shared.observability import get_logger, instrument_action
from xcron_libs.capabilities.reconciliation.state_store import (
    load_project_state,
    resolve_project_state_path,
)

LOGGER = get_logger(__name__)


def collect_cron_schedule_errors(jobs: tuple[NormalizedJob, ...]) -> tuple[PlanChange, ...]:
    """Compatibility facade for cron's reconciliation-owned validation rule."""
    return cron_schedule_errors(jobs)


@instrument_action("plan_project")
def plan_project(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    backend: str | None = None,
    state_root: str | Path | None = None,
    platform: str | None = None,
    scheduler_registry: SchedulerRegistry | None = None,
) -> PlanProjectResult:
    """Build a backend-neutral reconciliation plan for one project."""
    validation = validate_project(project_path, schedule_name=schedule_name)
    if not validation.valid or validation.normalized_manifest is None or validation.hashes is None:
        LOGGER.warning(
            "plan_validation_failed",
            project_root=validation.project_root,
            manifest_path=validation.manifest_path,
            error_count=len(validation.errors),
            warning_count=len(validation.warnings),
        )
        return PlanProjectResult(
            valid=False,
            validation=validation,
            backend=None,
            state_path=None,
        )

    selected_backend = backend or default_backend_for_current_platform(platform=platform)
    selected_scheduler = (scheduler_registry or default_scheduler_registry()).require(selected_backend)
    state = load_project_state(
        validation.normalized_manifest.project_id,
        backend=selected_backend,
        state_root=Path(state_root).expanduser().resolve() if state_root is not None else None,
    )
    state_path = resolve_project_state_path(
        validation.normalized_manifest.project_id,
        state_root=Path(state_root).expanduser().resolve() if state_root is not None else None,
    )
    plan = build_project_plan(
        validation.normalized_manifest,
        selected_backend,
        validation.hashes.manifest_hash,
        validation.hashes.job_hashes,
        validation.hashes.job_definition_hashes,
        state,
    )
    schedule_errors = selected_scheduler.schedule_errors(validation.normalized_manifest.jobs)
    if schedule_errors:
        plan = ProjectPlan(
            backend=plan.backend,
            manifest=plan.manifest,
            changes=plan.changes + schedule_errors,
            state=plan.state,
        )
    LOGGER.info(
        "project_plan_built",
        project_id=validation.normalized_manifest.project_id,
        backend=selected_backend,
        state_path=str(state_path),
        change_count=len(plan.changes),
        deployed_job_count=len(state.jobs),
    )
    return PlanProjectResult(
        valid=True,
        validation=validation,
        backend=selected_backend,
        state_path=str(state_path),
        changes=plan.changes,
        plan=plan,
    )

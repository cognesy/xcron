"""Plan desired-vs-deployed changes for one selected project schedule manifest."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from libs.actions.validate_project import ValidateProjectResult, validate_project
from libs.domain.diffing import PlanChange, PlanChangeKind, ProjectPlan, build_project_plan
from libs.domain.models import NormalizedJob, ScheduleKind
from libs.services import get_logger, instrument_action
from libs.services.state_store import (
    default_backend_for_current_platform,
    load_project_state,
    resolve_project_state_path,
)

LOGGER = get_logger(__name__)


def cron_incompatible_reason(job: NormalizedJob) -> str | None:
    """Return a reason string if this job's schedule cannot be expressed with cron, else None."""
    if job.schedule.kind is not ScheduleKind.EVERY:
        return None
    value = job.schedule.value
    suffix = value[-1]
    amount = int(value[:-1])
    if suffix == "s":
        return (
            f"cron cannot schedule sub-minute intervals (every={value}); "
            "use a minute-or-longer interval or switch to the launchd backend"
        )
    if suffix == "w" and amount > 1:
        return (
            f"cron cannot express multi-week intervals (every={value}); "
            "use a cron expression instead"
        )
    return None


def collect_cron_schedule_errors(jobs: tuple[NormalizedJob, ...]) -> tuple[PlanChange, ...]:
    """Return ERROR plan changes for any jobs whose schedules cannot be expressed with cron."""
    errors = []
    for job in jobs:
        reason = cron_incompatible_reason(job)
        if reason is not None:
            errors.append(
                PlanChange(
                    kind=PlanChangeKind.ERROR,
                    qualified_id=job.qualified_id,
                    reason=reason,
                    desired_job=job,
                )
            )
    return tuple(errors)


@dataclass(frozen=True)
class PlanProjectResult:
    """Structured result for the project planning use case."""

    valid: bool
    validation: ValidateProjectResult
    backend: str | None
    state_path: str | None
    changes: tuple[PlanChange, ...] = field(default_factory=tuple)
    plan: ProjectPlan | None = None


@instrument_action("plan_project")
def plan_project(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    backend: str | None = None,
    state_root: str | Path | None = None,
    platform: str | None = None,
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
    if selected_backend == "cron":
        cron_errors = collect_cron_schedule_errors(validation.normalized_manifest.jobs)
        if cron_errors:
            plan = ProjectPlan(
                backend=plan.backend,
                manifest=plan.manifest,
                changes=plan.changes + cron_errors,
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

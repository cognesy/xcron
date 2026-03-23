"""Apply one project's desired schedule state to the selected backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from libs.actions.plan_project import PlanProjectResult, collect_cron_schedule_errors
from libs.actions.status_project import status_project
from libs.domain import ProjectState
from libs.services import get_logger, instrument_action
from libs.services.backends.cron_service import apply_cron_plan
from libs.services.backends.launchd_service import apply_launchd_plan
from libs.services.state_store import resolve_project_state_path

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class ApplyProjectResult:
    """Structured result for the apply use case."""

    valid: bool
    backend: str | None
    plan_result: PlanProjectResult
    applied_state: ProjectState | None = None


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
) -> ApplyProjectResult:
    """Apply one project's desired state using the selected backend."""
    status_result = status_project(
        project_path,
        schedule_name=schedule_name,
        backend=backend,
        platform=platform,
        launch_agents_dir=launch_agents_dir,
        launchctl_domain=launchctl_domain,
        crontab_path=crontab_path,
    )
    if not status_result.valid or status_result.backend is None or status_result.plan is None:
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

    resolved_state_root = Path(state_root).expanduser().resolve() if state_root is not None else None
    plan_result = PlanProjectResult(
        valid=True,
        validation=status_result.validation,
        backend=status_result.backend,
        state_path=str(
            resolve_project_state_path(
                status_result.validation.normalized_manifest.project_id,
                state_root=resolved_state_root,
            )
        ),
        changes=status_result.plan.changes,
        plan=status_result.plan,
    )

    if plan_result.backend == "cron" and plan_result.plan is not None:
        cron_errors = collect_cron_schedule_errors(plan_result.plan.manifest.jobs)
        if cron_errors:
            LOGGER.error(
                "apply_cron_incompatible_schedules",
                project_id=plan_result.plan.manifest.project_id,
                incompatible_jobs=[e.qualified_id for e in cron_errors],
                reasons=[e.reason for e in cron_errors],
            )
            return ApplyProjectResult(valid=False, backend="cron", plan_result=plan_result)

    if plan_result.backend == "launchd":
        applied_state = apply_launchd_plan(
            plan_result,
            state_root=resolved_state_root,
            launch_agents_dir=Path(launch_agents_dir).expanduser().resolve() if launch_agents_dir is not None else None,
            domain_target=launchctl_domain,
            manage_launchctl=manage_launchctl,
        )
    elif plan_result.backend == "cron":
        applied_state = apply_cron_plan(
            plan_result,
            state_root=resolved_state_root,
            crontab_path=Path(crontab_path).expanduser().resolve() if crontab_path is not None else None,
            manage_crontab=manage_crontab,
        )
    else:
        raise ValueError(f"unsupported backend for apply: {plan_result.backend}")

    LOGGER.info(
        "project_applied",
        project_id=status_result.validation.normalized_manifest.project_id,
        backend=plan_result.backend,
        change_count=len(plan_result.changes),
        applied_job_count=len(applied_state.jobs),
        state_path=plan_result.state_path,
    )
    return ApplyProjectResult(
        valid=True,
        backend=plan_result.backend,
        plan_result=plan_result,
        applied_state=applied_state,
    )

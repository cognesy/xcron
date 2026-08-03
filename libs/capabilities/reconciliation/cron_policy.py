"""Cron-owned schedule compatibility policy."""

from __future__ import annotations

from xcron_libs.capabilities.reconciliation.domain import PlanChange, PlanChangeKind
from xcron_libs.domain import NormalizedJob, ScheduleKind


def cron_schedule_errors(jobs: tuple[NormalizedJob, ...]) -> tuple[PlanChange, ...]:
    """Return errors for portable schedules that cron cannot express."""
    errors: list[PlanChange] = []
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


def cron_incompatible_reason(job: NormalizedJob) -> str | None:
    """Return why cron cannot express a normalized schedule, if applicable."""
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

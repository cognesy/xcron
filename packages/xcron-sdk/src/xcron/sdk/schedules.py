"""Typed schedule-reconciliation API exposed by :class:`xcron.sdk.Xcron`."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from xcron.contracts import (
    ApplyProjectResult,
    InspectJobResult,
    InvocationContext,
    JobLookupRequest,
    PlanProjectResult,
    ProjectRequest,
    PruneProjectResult,
    ScheduleControlPort,
    SchedulerRequest,
    StatusProjectResult,
    UnknownSchedulerBackendError,
    ValidateProjectResult,
)
from xcron.sdk.errors import UnknownBackendError


ResultT = TypeVar("ResultT")


class SchedulesAPI:
    """Desired-state validation and native-scheduler reconciliation operations."""

    def __init__(
        self,
        scheduler: ScheduleControlPort,
        context: InvocationContext,
        guard: Callable[[], None],
    ) -> None:
        self._scheduler = scheduler
        self._context = context
        self._guard = guard

    def validate(self) -> ValidateProjectResult:
        return self._call(lambda: self._scheduler.validate(_project(self._context), self._context))

    def plan(self) -> PlanProjectResult:
        return self._call(lambda: self._scheduler.plan(_scheduler_request(self._context), self._context))

    def status(self) -> StatusProjectResult:
        return self._call(lambda: self._scheduler.status(_scheduler_request(self._context), self._context))

    def apply(self) -> ApplyProjectResult:
        return self._call(lambda: self._scheduler.apply(_scheduler_request(self._context), self._context))

    def inspect(self, job_identifier: str) -> InspectJobResult:
        return self._call(
            lambda: self._scheduler.inspect(
                JobLookupRequest(**_project(self._context).model_dump(), job_identifier=job_identifier),
                self._context,
            )
        )

    def prune(self) -> PruneProjectResult:
        return self._call(lambda: self._scheduler.prune(_scheduler_request(self._context), self._context))

    def _call(self, operation: Callable[[], ResultT]) -> ResultT:
        self._guard()
        try:
            return operation()
        except UnknownSchedulerBackendError as error:
            raise UnknownBackendError(str(error)) from error


def _project(context: InvocationContext) -> ProjectRequest:
    return ProjectRequest(
        project_path=context.options.project_path,
        schedule_name=context.options.schedule_name,
    )


def _scheduler_request(context: InvocationContext) -> SchedulerRequest:
    options = context.options
    return SchedulerRequest(
        project_path=options.project_path,
        schedule_name=options.schedule_name,
        backend=options.backend,
        state_root=options.state_root,
        platform=options.platform,
        launch_agents_dir=options.launch_agents_dir,
        launchctl_domain=options.launchctl_domain,
        crontab_path=options.crontab_path,
        manage_launchctl=options.manage_launchctl,
        manage_crontab=options.manage_crontab,
    )

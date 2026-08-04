"""Typed schedule-reconciliation API exposed by :class:`xcron_libs.Xcron`."""

from __future__ import annotations

from typing import Callable, TypeVar

from xcron_libs.capabilities.reconciliation.api import (
    SchedulerRegistry,
    apply_project,
    inspect_job,
    plan_project,
    prune_project,
    status_project,
    validate_project,
)
from xcron_libs.capabilities.reconciliation.contracts import (
    ApplyProjectResult,
    OutcomeRecorder,
    InspectJobResult,
    PlanProjectResult,
    PruneProjectResult,
    StatusProjectResult,
    UnknownSchedulerBackendError,
    ValidateProjectResult,
)
from xcron_libs.sdk.errors import UnknownBackendError
from xcron_libs.sdk.options import XcronOptions


ResultT = TypeVar("ResultT")


class SchedulesAPI:
    """Desired-state validation and native-scheduler reconciliation operations."""

    def __init__(
        self,
        options: XcronOptions,
        registry: SchedulerRegistry,
        outcome_recorder: OutcomeRecorder,
        guard: Callable[[], None],
    ) -> None:
        self._options = options
        self._registry = registry
        self._outcomes = outcome_recorder
        self._guard = guard

    def validate(self) -> ValidateProjectResult:
        return self._call(
            lambda: validate_project(
                self._options.project_path,
                schedule_name=self._options.schedule_name,
            ),
            requires_backend=False,
        )

    def plan(self) -> PlanProjectResult:
        return self._call(
            lambda: plan_project(
                self._options.project_path,
                schedule_name=self._options.schedule_name,
                backend=self._options.backend,
                state_root=self._options.state_root,
                platform=self._options.platform,
                scheduler_registry=self._registry,
            )
        )

    def status(self) -> StatusProjectResult:
        return self._call(
            lambda: status_project(
                self._options.project_path,
                schedule_name=self._options.schedule_name,
                backend=self._options.backend,
                platform=self._options.platform,
                launch_agents_dir=self._options.launch_agents_dir,
                launchctl_domain=self._options.launchctl_domain,
                crontab_path=self._options.crontab_path,
                scheduler_registry=self._registry,
                outcome_recorder=self._outcomes,
            )
        )

    def apply(self) -> ApplyProjectResult:
        return self._call(
            lambda: apply_project(
                self._options.project_path,
                schedule_name=self._options.schedule_name,
                backend=self._options.backend,
                state_root=self._options.state_root,
                platform=self._options.platform,
                launch_agents_dir=self._options.launch_agents_dir,
                launchctl_domain=self._options.launchctl_domain,
                crontab_path=self._options.crontab_path,
                manage_launchctl=self._options.manage_launchctl,
                manage_crontab=self._options.manage_crontab,
                scheduler_registry=self._registry,
                outcome_recorder=self._outcomes,
            )
        )

    def inspect(self, job_identifier: str) -> InspectJobResult:
        return self._call(
            lambda: inspect_job(
                job_identifier,
                self._options.project_path,
                schedule_name=self._options.schedule_name,
                backend=self._options.backend,
                platform=self._options.platform,
                launch_agents_dir=self._options.launch_agents_dir,
                launchctl_domain=self._options.launchctl_domain,
                crontab_path=self._options.crontab_path,
                scheduler_registry=self._registry,
                outcome_recorder=self._outcomes,
            )
        )

    def prune(self) -> PruneProjectResult:
        return self._call(
            lambda: prune_project(
                self._options.project_path,
                schedule_name=self._options.schedule_name,
                backend=self._options.backend,
                state_root=self._options.state_root,
                platform=self._options.platform,
                launch_agents_dir=self._options.launch_agents_dir,
                launchctl_domain=self._options.launchctl_domain,
                crontab_path=self._options.crontab_path,
                manage_launchctl=self._options.manage_launchctl,
                manage_crontab=self._options.manage_crontab,
                scheduler_registry=self._registry,
            )
        )

    def _call(
        self,
        operation: Callable[[], ResultT],
        *,
        requires_backend: bool = True,
    ) -> ResultT:
        self._guard()
        try:
            if requires_backend and self._options.backend is not None:
                self._registry.require(self._options.backend)
            return operation()
        except UnknownSchedulerBackendError as exc:
            raise UnknownBackendError(str(exc)) from exc

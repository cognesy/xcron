"""Typed schedule-reconciliation API exposed by :class:`xcron_libs.Xcron`."""

from __future__ import annotations

from typing import Callable

from xcron_libs.capabilities.reconciliation import (
    ApplyProjectResult,
    InspectJobResult,
    PlanProjectResult,
    PruneProjectResult,
    SchedulerRegistry,
    StatusProjectResult,
    ValidateProjectResult,
    apply_project,
    inspect_job,
    plan_project,
    prune_project,
    status_project,
    validate_project,
)
from xcron_libs.sdk.options import XcronOptions


class SchedulesAPI:
    """Desired-state validation and native-scheduler reconciliation operations."""

    def __init__(
        self,
        options: XcronOptions,
        registry: SchedulerRegistry,
        guard: Callable[[], None],
    ) -> None:
        self._options = options
        self._registry = registry
        self._guard = guard

    def validate(self) -> ValidateProjectResult:
        self._guard()
        return validate_project(
            self._options.project_path,
            schedule_name=self._options.schedule_name,
        )

    def plan(self) -> PlanProjectResult:
        self._guard()
        return plan_project(
            self._options.project_path,
            schedule_name=self._options.schedule_name,
            backend=self._options.backend,
            state_root=self._options.state_root,
            platform=self._options.platform,
            scheduler_registry=self._registry,
        )

    def status(self) -> StatusProjectResult:
        self._guard()
        return status_project(
            self._options.project_path,
            schedule_name=self._options.schedule_name,
            backend=self._options.backend,
            platform=self._options.platform,
            launch_agents_dir=self._options.launch_agents_dir,
            launchctl_domain=self._options.launchctl_domain,
            crontab_path=self._options.crontab_path,
            scheduler_registry=self._registry,
        )

    def apply(self) -> ApplyProjectResult:
        self._guard()
        return apply_project(
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

    def inspect(self, job_identifier: str) -> InspectJobResult:
        self._guard()
        return inspect_job(
            job_identifier,
            self._options.project_path,
            schedule_name=self._options.schedule_name,
            backend=self._options.backend,
            platform=self._options.platform,
            launch_agents_dir=self._options.launch_agents_dir,
            launchctl_domain=self._options.launchctl_domain,
            crontab_path=self._options.crontab_path,
            scheduler_registry=self._registry,
        )

    def prune(self) -> PruneProjectResult:
        self._guard()
        return prune_project(
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

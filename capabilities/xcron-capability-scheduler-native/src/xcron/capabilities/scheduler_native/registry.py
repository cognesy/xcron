"""Explicit registry of first-party native scheduler adapters.

This module also owns backend *selection*: which native scheduler xcron targets
when the caller does not name one.
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Mapping, Sequence

from xcron.capabilities.scheduler_native.contracts import (
    DeploymentPlan,
    SchedulerBackend,
    SchedulerInspection,
    SchedulerRuntimeOptions,
    UnknownSchedulerBackendError,
)
from xcron.capabilities.scheduler_native.layout import RuntimeLayout
from xcron.capabilities.scheduler_native.cron_policy import cron_schedule_errors
from xcron.capabilities.scheduler_native.domain import PlanChange, ProjectState
from xcron.contracts import NormalizedJob
from xcron.capabilities.scheduler_native.adapters.cron import (
    CronInspection,
    apply_cron_plan,
    collect_cron_project_state,
    inspect_cron_project,
    prune_cron_project,
)
from xcron.capabilities.scheduler_native.adapters.launchd import (
    LaunchdInspection,
    apply_launchd_plan,
    collect_launchd_project_state,
    inspect_launchd_project,
    prune_launchd_project,
)


@dataclass(frozen=True)
class LaunchdSchedulerBackend:
    """Typed adapter over xcron's first-party launchd service."""

    layout: RuntimeLayout
    name: str = "launchd"

    def collect_project_state(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> ProjectState:
        return collect_launchd_project_state(
            project_id,
            launch_agents_dir=options.launch_agents_dir,
            domain_target=options.launchctl_domain,
        )

    def inspect_project(
        self,
        project_id: str,
        *,
        options: SchedulerRuntimeOptions,
        include_native_detail: bool = False,
    ) -> tuple[SchedulerInspection, ...]:
        return tuple(
            _launchd_inspection(item)
            for item in inspect_launchd_project(
                project_id,
                launch_agents_dir=options.launch_agents_dir,
                domain_target=options.launchctl_domain,
                include_launchctl_print=include_native_detail,
            )
        )

    def apply(
        self, deployment: DeploymentPlan, *, options: SchedulerRuntimeOptions
    ) -> ProjectState:
        return apply_launchd_plan(
            deployment,
            layout=self.layout,
            state_root=options.state_root,
            launch_agents_dir=options.launch_agents_dir,
            domain_target=options.launchctl_domain,
            manage_launchctl=options.manage_launchctl,
        )

    def prune_project(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> tuple[SchedulerInspection, ...]:
        return tuple(
            _launchd_inspection(item)
            for item in prune_launchd_project(
                project_id,
                launch_agents_dir=options.launch_agents_dir,
                domain_target=options.launchctl_domain,
                manage_launchctl=options.manage_launchctl,
            )
        )

    def schedule_errors(self, jobs: tuple[NormalizedJob, ...]) -> tuple[PlanChange, ...]:
        return tuple()


@dataclass(frozen=True)
class CronSchedulerBackend:
    """Typed adapter over xcron's first-party cron service."""

    layout: RuntimeLayout
    name: str = "cron"

    def collect_project_state(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> ProjectState:
        return collect_cron_project_state(project_id, crontab_path=options.crontab_path)

    def inspect_project(
        self,
        project_id: str,
        *,
        options: SchedulerRuntimeOptions,
        include_native_detail: bool = False,
    ) -> tuple[SchedulerInspection, ...]:
        return tuple(
            _cron_inspection(item)
            for item in inspect_cron_project(
                project_id, crontab_path=options.crontab_path
            )
        )

    def apply(
        self, deployment: DeploymentPlan, *, options: SchedulerRuntimeOptions
    ) -> ProjectState:
        return apply_cron_plan(
            deployment,
            layout=self.layout,
            state_root=options.state_root,
            crontab_path=options.crontab_path,
            manage_crontab=options.manage_crontab,
        )

    def prune_project(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> tuple[SchedulerInspection, ...]:
        return tuple(
            _cron_inspection(item)
            for item in prune_cron_project(
                project_id,
                crontab_path=options.crontab_path,
                manage_crontab=options.manage_crontab,
            )
        )

    def schedule_errors(self, jobs: tuple[NormalizedJob, ...]) -> tuple[PlanChange, ...]:
        return cron_schedule_errors(jobs)


class SchedulerRegistry:
    """Resolve stable scheduler identities without implicit discovery."""

    def __init__(self, backends: Sequence[SchedulerBackend]) -> None:
        indexed: dict[str, SchedulerBackend] = {}
        for backend in backends:
            if backend.name in indexed:
                raise ValueError(f"duplicate scheduler backend: {backend.name}")
            indexed[backend.name] = backend
        self._backends: Mapping[str, SchedulerBackend] = indexed

    def require(self, backend_name: str) -> SchedulerBackend:
        try:
            return self._backends[backend_name]
        except KeyError as exc:
            raise UnknownSchedulerBackendError(backend_name, self.names) from exc

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._backends))


def default_scheduler_registry(layout: RuntimeLayout) -> SchedulerRegistry:
    """Build the deterministic first-party scheduler registry."""
    return SchedulerRegistry((LaunchdSchedulerBackend(layout), CronSchedulerBackend(layout)))


def _launchd_inspection(item: LaunchdInspection) -> SchedulerInspection:
    return SchedulerInspection(
        qualified_id=item.qualified_id,
        job_id=item.job_id,
        artifact_path=str(item.plist_path),
        wrapper_path=item.wrapper_path,
        enabled=item.enabled,
        desired_hash=item.desired_hash,
        definition_hash=item.definition_hash,
        stdout_log_path=item.stdout_log_path,
        stderr_log_path=item.stderr_log_path,
        event_log_path=item.event_log_path,
        label=item.label,
        loaded=item.loaded,
        raw_plist=item.raw_plist,
        launchctl_print=item.launchctl_print,
    )


def _cron_inspection(item: CronInspection) -> SchedulerInspection:
    return SchedulerInspection(
        qualified_id=item.qualified_id,
        job_id=item.job_id,
        artifact_path=item.artifact_path,
        wrapper_path=item.wrapper_path,
        enabled=item.enabled,
        desired_hash=item.desired_hash,
        definition_hash=item.definition_hash,
        stdout_log_path=item.stdout_log_path,
        stderr_log_path=item.stderr_log_path,
        event_log_path=item.event_log_path,
        raw_entry=item.raw_entry,
    )


def default_backend_for_current_platform(platform: str | None = None) -> str:
    """Return the backend xcron should target on the current platform."""
    selected = sys.platform if platform is None else platform
    if selected.startswith("darwin"):
        return "launchd"
    if selected.startswith("linux"):
        return "cron"
    raise ValueError(f"unsupported platform for xcron prototype: {selected}")

"""Backend-neutral contracts owned by schedule reconciliation.

These contracts are deliberately independent of action result and CLI response
types. Scheduler adapters consume only the validated deployment data they need
to render, inspect, apply, or prune native artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from xcron_libs.domain import (
    NormalizedJob,
    PlanChange,
    ProjectPlan,
    ProjectState,
)


@dataclass(frozen=True)
class DeploymentPlan:
    """Validated backend-neutral data required to apply one project plan."""

    backend: str
    plan: ProjectPlan
    state_path: str
    manifest_hash: str
    job_hashes: Mapping[str, str]
    job_definition_hashes: Mapping[str, str]


@dataclass(frozen=True)
class SchedulerRuntimeOptions:
    """Explicit host paths and mutation controls for one scheduler operation."""

    state_root: Path | None = None
    launch_agents_dir: Path | None = None
    launchctl_domain: str | None = None
    crontab_path: Path | None = None
    manage_launchctl: bool = True
    manage_crontab: bool = True

    @classmethod
    def create(
        cls,
        *,
        state_root: str | Path | None = None,
        launch_agents_dir: str | Path | None = None,
        launchctl_domain: str | None = None,
        crontab_path: str | Path | None = None,
        manage_launchctl: bool = True,
        manage_crontab: bool = True,
    ) -> SchedulerRuntimeOptions:
        """Normalize direct/legacy path inputs at the scheduler-port boundary."""
        return cls(
            state_root=_resolve_path(state_root),
            launch_agents_dir=_resolve_path(launch_agents_dir),
            launchctl_domain=launchctl_domain,
            crontab_path=_resolve_path(crontab_path),
            manage_launchctl=manage_launchctl,
            manage_crontab=manage_crontab,
        )


@dataclass(frozen=True)
class SchedulerInspection:
    """Backend-neutral view of one xcron-owned native scheduler artifact."""

    qualified_id: str
    job_id: str | None
    artifact_path: str | None
    wrapper_path: Path | None
    enabled: bool
    desired_hash: str | None
    definition_hash: str | None
    stdout_log_path: Path | None = None
    stderr_log_path: Path | None = None
    event_log_path: Path | None = None
    label: str | None = None
    loaded: bool | None = None
    raw_entry: str | None = None
    raw_plist: Mapping[str, Any] | None = None
    launchctl_print: str | None = None


class SchedulerBackend(Protocol):
    """Trusted in-process adapter for one native scheduler implementation."""

    name: str

    def collect_project_state(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> ProjectState:
        """Return actual deployed state owned by this backend."""

    def inspect_project(
        self,
        project_id: str,
        *,
        options: SchedulerRuntimeOptions,
        include_native_detail: bool = False,
    ) -> tuple[SchedulerInspection, ...]:
        """Return backend-native inspection records for one project."""

    def apply(
        self, deployment: DeploymentPlan, *, options: SchedulerRuntimeOptions
    ) -> ProjectState:
        """Apply a validated desired-vs-actual plan."""

    def prune_project(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> tuple[SchedulerInspection, ...]:
        """Remove only artifacts owned by xcron for one project."""

    def schedule_errors(self, jobs: tuple[NormalizedJob, ...]) -> tuple[PlanChange, ...]:
        """Return backend-specific schedule incompatibilities for planning."""


def _resolve_path(value: str | Path | None) -> Path | None:
    return Path(value).expanduser().resolve() if value is not None else None

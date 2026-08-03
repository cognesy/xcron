"""Public contracts owned by the schedule-reconciliation module.

This module is one of the two entry points outside code may import; the other
is :mod:`xcron_libs.capabilities.reconciliation.api`. It owns three families of
value:

* the backend-neutral deployment and inspection data a scheduler adapter needs;
* the typed scheduler port those adapters implement; and
* the use-case results returned by the module's public API.

Nothing here depends on a channel, renderer, or CLI response type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from xcron_libs.domain import (
    NormalizedJob,
    NormalizedManifest,
    PlanChange,
    ProjectPlan,
    ProjectState,
    StatusEntry,
)
from xcron_libs.services.hash_service import ManifestHashes
from xcron_libs.services.schema_validator import ValidationMessage


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


class UnknownSchedulerBackendError(ValueError):
    """Raised when a scheduler identity is absent from the active registry."""

    def __init__(self, backend_name: str, available: tuple[str, ...]) -> None:
        self.backend_name = backend_name
        self.available = available
        available_text = ", ".join(available) or "none"
        super().__init__(
            f"unsupported scheduler backend: {backend_name} (available: {available_text})"
        )


@dataclass(frozen=True)
class ValidateProjectResult:
    """Structured result for the validate use case."""

    project_root: str
    manifest_path: str | None
    valid: bool
    errors: tuple[ValidationMessage, ...] = field(default_factory=tuple)
    warnings: tuple[ValidationMessage, ...] = field(default_factory=tuple)
    normalized_manifest: NormalizedManifest | None = None
    hashes: ManifestHashes | None = None


@dataclass(frozen=True)
class PlanProjectResult:
    """Structured result for the project planning use case."""

    valid: bool
    validation: ValidateProjectResult
    backend: str | None
    state_path: str | None
    changes: tuple[PlanChange, ...] = field(default_factory=tuple)
    plan: ProjectPlan | None = None


@dataclass(frozen=True)
class StatusProjectResult:
    """Structured result for the status use case."""

    valid: bool
    backend: str | None
    validation: ValidateProjectResult
    plan: ProjectPlan | None = None
    statuses: tuple[StatusEntry, ...] = field(default_factory=tuple)
    inspections: tuple[SchedulerInspection, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ApplyProjectResult:
    """Structured result for the apply use case."""

    valid: bool
    backend: str | None
    plan_result: PlanProjectResult
    applied_state: ProjectState | None = None


@dataclass(frozen=True)
class PruneProjectResult:
    """Structured result for the prune use case."""

    valid: bool
    backend: str | None
    project_id: str | None
    removed: tuple[SchedulerInspection, ...] = field(default_factory=tuple)
    error: str | None = None


@dataclass(frozen=True)
class InspectField:
    """One structured field shown in inspect output."""

    name: str
    value: str


@dataclass(frozen=True)
class InspectSnippet:
    """One backend-native snippet shown in inspect output."""

    name: str
    content: str


@dataclass(frozen=True)
class InspectJobResult:
    """Structured result for the inspect use case."""

    valid: bool
    backend: str | None
    status: StatusProjectResult
    desired_job: NormalizedJob | None = None
    status_entry: StatusEntry | None = None
    desired_fields: tuple[InspectField, ...] = field(default_factory=tuple)
    deployed_fields: tuple[InspectField, ...] = field(default_factory=tuple)
    snippets: tuple[InspectSnippet, ...] = field(default_factory=tuple)
    inspection: SchedulerInspection | None = None
    error: str | None = None


def _resolve_path(value: str | Path | None) -> Path | None:
    return Path(value).expanduser().resolve() if value is not None else None

"""Public contracts owned by the schedule-reconciliation module.

This module is one of the two entry points outside code may import; the other
is :mod:`xcron.capabilities.reconciliation.api`. It owns the use-case
results the module's public API returns, plus the stable errors it raises.

The ports themselves live in
:mod:`xcron.capabilities.reconciliation.ports`; the port values a caller
must name — to supply a scheduler, or an outcome recorder — are re-exported
here so callers need only one import.

Nothing here depends on a channel, renderer, or CLI response type.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xcron.capabilities.reconciliation.domain import (
    DeployedJobState,
    PlanChange,
    PlanChangeKind,
    ProjectPlan,
    ProjectState,
    StatusEntry,
    StatusKind,
)
from xcron.capabilities.manifest.contracts import ManifestHashes, ValidationMessage
from xcron.capabilities.reconciliation.ports import (
    DeploymentPlan,
    NullOutcomeRecorder,
    OutcomeRecorder,
    SchedulerBackend,
    SchedulerInspection,
    SchedulerRuntimeOptions,
)
from xcron.domain import NormalizedJob, NormalizedManifest

__all__ = [
    "ApplyProjectResult",
    "DeployedJobState",
    "DeploymentPlan",
    "InspectField",
    "InspectJobResult",
    "InspectSnippet",
    "NullOutcomeRecorder",
    "OutcomeRecorder",
    "PlanChange",
    "PlanChangeKind",
    "PlanProjectResult",
    "ProjectPlan",
    "ProjectState",
    "PruneProjectResult",
    "SchedulerBackend",
    "SchedulerInspection",
    "SchedulerRuntimeOptions",
    "StatusEntry",
    "StatusKind",
    "StatusProjectResult",
    "UnknownSchedulerBackendError",
    "ValidateProjectResult",
]


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

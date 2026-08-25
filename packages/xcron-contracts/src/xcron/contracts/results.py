"""Stable, implementation-free results and errors for xcron provider ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping

from xcron.contracts.domain import ManifestHashes, NormalizedJob, ValidationMessage

__all__ = [
    "AgentHooksError",
    "ApplyProjectResult",
    "ClaudeHookStatus",
    "ConfigurationError",
    "CodexHookStatus",
    "DeployedJobState",
    "ExecutableNotFoundError",
    "HookInstallResult",
    "HookStatusResult",
    "InspectField",
    "InspectJobResult",
    "InspectSnippet",
    "JobActionResult",
    "LoadedManifestDocument",
    "LogFileEntry",
    "LogsClearResult",
    "LogsListResult",
    "ManifestError",
    "ManifestMutationResult",
    "ManifestNotFoundError",
    "MetricsResetResult",
    "MetricsResult",
    "PlanChange",
    "PlanChangeKind",
    "PlanProjectResult",
    "ProjectPlan",
    "ProjectState",
    "PruneProjectResult",
    "SchedulerInspection",
    "SessionEndResult",
    "StatusEntry",
    "StatusKind",
    "StatusProjectResult",
    "UnknownSchedulerBackendError",
    "UnsupportedMarkerSchemaError",
    "UnsupportedPlatformError",
    "ValidateProjectResult",
    "MalformedMarkerError",
    "WorkspaceError",
    "WorkspaceMarkerError",
    "WorkspaceResolutionError",
    "XcronContractError",
]


class XcronContractError(Exception):
    """Base failure a channel or another provider may handle intentionally."""


class ConfigurationError(XcronContractError):
    """Settings composition failed before an invocation could be constructed."""


class WorkspaceError(XcronContractError):
    """Workspace identity or layout could not be trusted."""


class WorkspaceResolutionError(WorkspaceError):
    """A requested workspace path was absent or unusable."""


class UnsupportedPlatformError(WorkspaceError):
    """The host platform has no defined xcron state-root convention."""


class WorkspaceMarkerError(WorkspaceError):
    """A present workspace marker cannot be trusted."""


class MalformedMarkerError(WorkspaceMarkerError):
    """A workspace marker is unreadable, malformed, or the wrong shape."""


class UnsupportedMarkerSchemaError(WorkspaceMarkerError):
    """A workspace marker declares an unsupported compatibility schema."""


class ManifestError(XcronContractError):
    """Manifest loading, parsing, validation, or editing failed."""


class ManifestNotFoundError(ManifestError):
    """No selected manifest exists for the requested workspace."""


class UnknownSchedulerBackendError(XcronContractError):
    """The selected scheduler is not offered by the active provider set."""

    def __init__(self, backend_name: str, available: tuple[str, ...]) -> None:
        self.backend_name = backend_name
        self.available = available
        available_text = ", ".join(available) or "none"
        super().__init__(
            f"unsupported scheduler backend: {backend_name} (available: {available_text})"
        )


class AgentHooksError(XcronContractError):
    """Agent-hook installation or inspection failed."""


class ExecutableNotFoundError(AgentHooksError):
    """A hook cannot resolve the xcron executable it must invoke."""


@dataclass(frozen=True, slots=True)
class LoadedManifestDocument:
    """A loaded manifest with opaque boundary data retained for YAML edits."""

    project_root: Path
    manifest_path: Path
    raw_data: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ManifestMutationResult:
    """Result of one atomically validated manifest mutation."""

    project_root: str
    manifest_path: str
    changed: bool
    raw_jobs: tuple[Mapping[str, object], ...] = ()
    raw_job: Mapping[str, object] | None = None
    warnings: tuple[ValidationMessage, ...] = ()


@dataclass(frozen=True, slots=True)
class JobActionResult:
    """Result of a list, read, or YAML-only job mutation."""

    valid: bool
    project_root: str
    manifest_path: str | None
    validation: ValidateProjectResult | None = None
    jobs: tuple[NormalizedJob, ...] = ()
    raw_jobs: tuple[Mapping[str, object], ...] = ()
    job: NormalizedJob | None = None
    raw_job: Mapping[str, object] | None = None
    removed_job_identifier: str | None = None
    changed: bool = True
    warnings: tuple[ValidationMessage, ...] = ()
    error: str | None = None


class PlanChangeKind(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"
    ENABLE = "enable"
    DISABLE = "disable"
    NOOP = "noop"
    DRIFT = "drift"
    ERROR = "error"


class StatusKind(str, Enum):
    OK = "ok"
    MISSING = "missing"
    DRIFT = "drift"
    DISABLED = "disabled"
    EXTRA = "extra"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class DeployedJobState:
    qualified_id: str
    job_id: str
    artifact_id: str
    backend: str
    enabled: bool
    desired_hash: str
    definition_hash: str | None = None
    observed_hash: str | None = None
    label: str | None = None
    artifact_path: str | None = None
    wrapper_path: str | None = None
    stdout_log_path: str | None = None
    stderr_log_path: str | None = None
    event_log_path: str | None = None
    last_applied_at: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectState:
    """Derived local record for one project deployed on this machine."""

    project_id: str
    backend: str
    manifest_hash: str | None
    jobs: tuple[DeployedJobState, ...] = ()
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class PlanChange:
    kind: PlanChangeKind
    qualified_id: str
    reason: str
    desired_job: NormalizedJob | None = None
    deployed_job: DeployedJobState | None = None
    desired_hash: str | None = None
    deployed_hash: str | None = None


@dataclass(frozen=True, slots=True)
class StatusEntry:
    kind: StatusKind
    qualified_id: str
    reason: str
    desired_job: NormalizedJob | None = None
    deployed_job: DeployedJobState | None = None


@dataclass(frozen=True, slots=True)
class ProjectPlan:
    """The native provider's complete desired-versus-deployed projection."""

    backend: str
    manifest: NormalizedManifest
    changes: tuple[PlanChange, ...]
    state: ProjectState


@dataclass(frozen=True, slots=True)
class SchedulerInspection:
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
    raw_plist: Mapping[str, object] | None = None
    launchctl_print: str | None = None


@dataclass(frozen=True, slots=True)
class ValidateProjectResult:
    project_root: str
    manifest_path: str | None
    valid: bool
    errors: tuple[ValidationMessage, ...] = ()
    warnings: tuple[ValidationMessage, ...] = ()
    normalized_manifest: NormalizedManifest | None = None
    hashes: ManifestHashes | None = None


@dataclass(frozen=True, slots=True)
class PlanProjectResult:
    valid: bool
    validation: ValidateProjectResult
    backend: str | None
    state_path: str | None
    changes: tuple[PlanChange, ...] = ()
    plan: ProjectPlan | None = None


@dataclass(frozen=True, slots=True)
class StatusProjectResult:
    valid: bool
    backend: str | None
    validation: ValidateProjectResult
    plan: ProjectPlan | None = None
    statuses: tuple[StatusEntry, ...] = ()
    inspections: tuple[SchedulerInspection, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplyProjectResult:
    valid: bool
    backend: str | None
    plan_result: PlanProjectResult
    applied_state: ProjectState | None = None


@dataclass(frozen=True, slots=True)
class PruneProjectResult:
    valid: bool
    backend: str | None
    project_id: str | None
    removed: tuple[SchedulerInspection, ...] = ()
    error: str | None = None


@dataclass(frozen=True, slots=True)
class InspectField:
    name: str
    value: str


@dataclass(frozen=True, slots=True)
class InspectSnippet:
    name: str
    content: str


@dataclass(frozen=True, slots=True)
class InspectJobResult:
    valid: bool
    backend: str | None
    status: StatusProjectResult
    desired_job: NormalizedJob | None = None
    status_entry: StatusEntry | None = None
    desired_fields: tuple[InspectField, ...] = ()
    deployed_fields: tuple[InspectField, ...] = ()
    snippets: tuple[InspectSnippet, ...] = ()
    inspection: SchedulerInspection | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LogFileEntry:
    qualified_id: str
    kind: str
    path: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class LogsListResult:
    valid: bool
    project_id: str | None = None
    logs_dir: str | None = None
    files: tuple[LogFileEntry, ...] = ()
    validation: ValidateProjectResult | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LogsClearResult:
    valid: bool
    project_id: str | None = None
    dry_run: bool = True
    files: tuple[LogFileEntry, ...] = ()
    cleared: int = 0
    validation: ValidateProjectResult | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MetricsResult:
    path: str
    version: int
    created_at: str
    updated_at: str
    counters: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class MetricsResetResult(MetricsResult):
    previous_counters: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class CodexHookStatus:
    config_path: str
    hooks_path: str
    config_exists: bool
    hooks_exists: bool
    feature_enabled: bool
    session_start_matches: bool
    session_end_matches: bool


@dataclass(frozen=True, slots=True)
class ClaudeHookStatus:
    settings_path: str
    settings_exists: bool
    session_start_matches: bool
    stop_matches: bool


@dataclass(frozen=True, slots=True)
class HookInstallResult:
    executable_path: str
    codex_config_path: str
    codex_hooks_path: str
    claude_settings_path: str
    changed_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HookStatusResult:
    executable_path: str
    codex: CodexHookStatus
    claude: ClaudeHookStatus


@dataclass(frozen=True, slots=True)
class SessionEndResult:
    log_path: str

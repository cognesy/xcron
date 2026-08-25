"""Runtime-checkable public ports implemented by xcron capability packages."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

from xcron.contracts.domain import (
    InvocationContext,
    ManifestHashes,
    NormalizedJob,
    NormalizedManifest,
    OutcomeSink,
    ProjectWorkspace,
    RuntimePaths,
    Settings,
    ValidationReport,
    WorkspaceInitResult,
    XcronHome,
    XcronOptions,
)
from xcron.contracts.requests import (
    HookRequest,
    JobCreateRequest,
    JobLookupRequest,
    JobUpdateRequest,
    LogsRequest,
    ProjectRequest,
    SchedulerRequest,
)
from xcron.contracts.results import (
    ApplyProjectResult,
    HookInstallResult,
    HookStatusResult,
    InspectJobResult,
    JobActionResult,
    LoadedManifestDocument,
    LogsClearResult,
    LogsListResult,
    ManifestMutationResult,
    MetricsResetResult,
    MetricsResult,
    PlanProjectResult,
    PruneProjectResult,
    SessionEndResult,
    StatusProjectResult,
    ValidateProjectResult,
)


@runtime_checkable
class WorkspacePort(Protocol):
    """Resolve project identity and derived local layouts."""

    def resolve_workspace(
        self,
        request: ProjectRequest,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> ProjectWorkspace: ...
    def initialize(self, root: Path | None, *, created_by: str) -> WorkspaceInitResult: ...
    def home(self, root: Path | None = None) -> XcronHome: ...
    def runtime_paths(self, job: NormalizedJob, *, state_root: Path | None = None) -> RuntimePaths: ...
    def project_state_path(self, project_id: str, *, state_root: Path | None = None) -> Path: ...


@runtime_checkable
class SettingsPort(Protocol):
    """Compose strict settings from an explicit environment snapshot."""

    def compose(
        self,
        workspace: ProjectWorkspace | None,
        options: XcronOptions,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> Settings: ...


@runtime_checkable
class ObservabilityPort(Protocol):
    """Make a best-effort outcome sink for an already-composed invocation."""

    def outcome_sink(self, context: InvocationContext) -> OutcomeSink: ...


@runtime_checkable
class ManifestPort(Protocol):
    """Load, validate, normalize, hash, and atomically edit one manifest."""

    def load(self, request: ProjectRequest, context: InvocationContext) -> LoadedManifestDocument: ...
    def validate(self, document: LoadedManifestDocument, context: InvocationContext) -> ValidationReport: ...
    def normalize(self, document: LoadedManifestDocument, context: InvocationContext) -> NormalizedManifest: ...
    def hashes(self, manifest: NormalizedManifest) -> ManifestHashes: ...
    def list_jobs(self, request: ProjectRequest, context: InvocationContext) -> tuple[Mapping[str, object], ...]: ...
    def get_job(self, request: JobLookupRequest, context: InvocationContext) -> Mapping[str, object]: ...
    def create_job(self, request: JobCreateRequest, context: InvocationContext) -> ManifestMutationResult: ...
    def remove_job(self, request: JobLookupRequest, context: InvocationContext) -> ManifestMutationResult: ...
    def edit(self, request: JobLookupRequest, mutation: JobUpdateRequest, context: InvocationContext) -> ManifestMutationResult: ...
    def set_job_enabled(
        self,
        request: JobLookupRequest,
        enabled: bool,
        context: InvocationContext,
    ) -> ManifestMutationResult: ...


@runtime_checkable
class ScheduleControlPort(Protocol):
    """Validate and reconcile desired schedules to one native scheduler."""

    def validate(self, request: ProjectRequest, context: InvocationContext) -> ValidateProjectResult: ...
    def plan(self, request: SchedulerRequest, context: InvocationContext) -> PlanProjectResult: ...
    def status(self, request: SchedulerRequest, context: InvocationContext) -> StatusProjectResult: ...
    def apply(self, request: SchedulerRequest, context: InvocationContext) -> ApplyProjectResult: ...
    def prune(self, request: SchedulerRequest, context: InvocationContext) -> PruneProjectResult: ...
    def inspect(self, request: JobLookupRequest, context: InvocationContext) -> InspectJobResult: ...


@runtime_checkable
class JobManagementPort(Protocol):
    """Read and mutate YAML jobs without touching scheduler artifacts."""

    def list(self, request: ProjectRequest, context: InvocationContext) -> JobActionResult: ...
    def show(self, request: JobLookupRequest, context: InvocationContext) -> JobActionResult: ...
    def create(self, request: JobCreateRequest, context: InvocationContext) -> JobActionResult: ...
    def update(self, request: JobLookupRequest, mutation: JobUpdateRequest, context: InvocationContext) -> JobActionResult: ...
    def enable(self, request: JobLookupRequest, context: InvocationContext) -> JobActionResult: ...
    def disable(self, request: JobLookupRequest, context: InvocationContext) -> JobActionResult: ...
    def remove(self, request: JobLookupRequest, context: InvocationContext) -> JobActionResult: ...


@runtime_checkable
class LogPort(Protocol):
    """List and clear only owned wrapper logs."""

    def list(self, request: LogsRequest, context: InvocationContext) -> LogsListResult: ...
    def clear(self, request: LogsRequest, context: InvocationContext) -> LogsClearResult: ...


@runtime_checkable
class MetricsPort(Protocol):
    """Read and reset the best-effort metrics store."""

    def show(self, context: InvocationContext) -> MetricsResult: ...
    def reset(self, context: InvocationContext) -> MetricsResetResult: ...
    def outcome_sink(self, context: InvocationContext) -> OutcomeSink: ...


@runtime_checkable
class AgentHooksPort(Protocol):
    """Install, inspect, repair, and record the agent-hook integration."""

    def install(self, request: HookRequest, context: InvocationContext) -> HookInstallResult: ...
    def status(self, request: HookRequest, context: InvocationContext) -> HookStatusResult: ...
    def repair(self, request: HookRequest, context: InvocationContext) -> HookInstallResult: ...
    def record_session_end(self, request: ProjectRequest, context: InvocationContext) -> SessionEndResult: ...

"""Implementation-free values shared by xcron capability packages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


DEFAULT_WORKING_DIR = "."
DEFAULT_SHELL = "/bin/zsh"
SUPPORTED_EVERY_SUFFIXES = ("s", "m", "h", "d", "w")


class ScheduleKind(str, Enum):
    """Backend-neutral schedule kinds supported by xcron v1."""

    CRON = "cron"
    EVERY = "every"


class OverlapPolicy(str, Enum):
    """Execution overlap policies supported by xcron v1."""

    ALLOW = "allow"
    FORBID = "forbid"


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Project-scoped metadata loaded from a selected schedule manifest."""

    id: str


@dataclass(frozen=True, slots=True)
class DefaultsConfig:
    """Manifest defaults merged into job definitions during normalization."""

    working_dir: str = DEFAULT_WORKING_DIR
    shell: str = DEFAULT_SHELL
    timezone: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    """Raw schedule definition from a manifest."""

    kind: ScheduleKind
    value: str


@dataclass(frozen=True, slots=True)
class JobDefinition:
    """Raw job definition from a manifest."""

    id: str
    command: str
    schedule: ScheduleDefinition
    description: str | None = None
    enabled: bool = True
    working_dir: str | None = None
    shell: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    overlap: OverlapPolicy = OverlapPolicy.ALLOW


@dataclass(frozen=True, slots=True)
class ProjectManifest:
    """Complete raw manifest model before normalization."""

    version: int
    project: ProjectConfig
    jobs: tuple[JobDefinition, ...]
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)


@dataclass(frozen=True, slots=True)
class NormalizedExecutionConfig:
    """Resolved execution settings for one job."""

    command: str
    working_dir: str
    shell: str
    timezone: str | None
    env: tuple[tuple[str, str], ...]
    overlap: OverlapPolicy


@dataclass(frozen=True, slots=True)
class NormalizedJob:
    """Deterministic per-job model consumed by planners and backends."""

    project_id: str
    job_id: str
    qualified_id: str
    artifact_id: str
    enabled: bool
    schedule: ScheduleDefinition
    execution: NormalizedExecutionConfig
    description: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedManifest:
    """Project-scoped normalized manifest."""

    version: int
    project_id: str
    project_root: str
    manifest_path: str
    jobs: tuple[NormalizedJob, ...]


@dataclass(frozen=True, slots=True)
class ValidationMessage:
    """One structured schema or semantic validation diagnostic."""

    level: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Typed validation outcome without a provider-specific projection."""

    valid: bool
    errors: tuple[ValidationMessage, ...] = ()
    warnings: tuple[ValidationMessage, ...] = ()
    normalized_manifest: NormalizedManifest | None = None


@dataclass(frozen=True, slots=True)
class ManifestHashes:
    """Stable hashes for one normalized project manifest."""

    manifest_hash: str
    job_hashes: Mapping[str, str]
    job_definition_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class WorkspaceMarker:
    """Versioned identity marker for a project workspace."""

    kind: str
    schema: int
    created_by: str


@dataclass(frozen=True, slots=True)
class ProjectWorkspace:
    """One resolved workspace and its local configuration locations."""

    root: Path
    manifest_dir: Path
    config_path: Path
    marker_path: Path
    marker: WorkspaceMarker | None

    @property
    def is_marked(self) -> bool:
        return self.marker is not None


@dataclass(frozen=True, slots=True)
class XcronHome:
    """The layout of the per-user xcron home directory."""

    root: Path
    schedules_dir: Path
    manifest_path: Path
    metrics_path: Path
    marker_path: Path


@dataclass(frozen=True, slots=True)
class WorkspaceInitResult:
    """The observable outcome of non-destructive workspace initialization."""

    xcron_home: str
    schedules_dir: str
    manifest_path: str
    marker_path: str
    created: bool
    created_paths: tuple[str, ...]
    retained_paths: tuple[str, ...]
    migrated_paths: tuple[str, ...]
    conflicts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """Managed runtime paths for one normalized job."""

    project_dir: Path
    wrappers_dir: Path
    logs_dir: Path
    locks_dir: Path
    wrapper_path: Path
    stdout_log_path: Path
    stderr_log_path: Path
    event_log_path: Path
    lock_path: Path


class Settings(BaseModel):
    """Effective host and scheduler settings for one invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_root: Path | None = None
    launch_agents_dir: Path | None = None
    launchctl_domain: str | None = None
    crontab_path: Path | None = None
    manage_launchctl: bool = True
    manage_crontab: bool = True


@dataclass(frozen=True, slots=True)
class XcronOptions:
    """Immutable invocation scope supplied by a channel or SDK client."""

    project_path: Path | None = None
    schedule_name: str | None = None
    backend: str | None = None
    state_root: Path | None = None
    platform: str | None = None
    launch_agents_dir: Path | None = None
    launchctl_domain: str | None = None
    crontab_path: Path | None = None
    manage_launchctl: bool = True
    manage_crontab: bool = True

    @classmethod
    def create(
        cls,
        project_path: str | Path | None = None,
        **kwargs: object,
    ) -> XcronOptions:
        """Normalize direct path inputs without reading process state."""
        path_names = {"state_root", "launch_agents_dir", "crontab_path"}
        values = {
            name: _resolve_path(value) if name in path_names else value
            for name, value in kwargs.items()
        }
        return cls(project_path=_resolve_path(project_path), **values)


@runtime_checkable
class OutcomeSink(Protocol):
    """Best-effort operational outcome sink; implementations never raise."""

    def record(self, counter: str, amount: int = 1) -> None:
        """Record an outcome without becoming a control-plane prerequisite."""


class NullOutcomeSink:
    """An inert sink for lean or unavailable observability installations."""

    def record(self, counter: str, amount: int = 1) -> None:
        return None


@dataclass(frozen=True, slots=True)
class InvocationContext:
    """One already-composed invocation passed explicitly to providers."""

    options: XcronOptions
    workspace: ProjectWorkspace | None
    settings: Settings
    event_sink: OutcomeSink = field(default_factory=NullOutcomeSink)


def stable_env_items(env: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """Return a stable, sorted representation of environment mappings."""
    return tuple(sorted((str(key), str(value)) for key, value in env.items()))


def build_qualified_job_id(project_id: str, job_id: str) -> str:
    """Build the backend-neutral fully-qualified job identity."""
    return f"{project_id}.{job_id}"


def build_artifact_id(project_id: str, job_id: str) -> str:
    """Build a filesystem and scheduler-friendly identifier."""
    qualified_id = build_qualified_job_id(project_id, job_id)
    return "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in qualified_id)


def resolve_working_dir(project_root: Path, value: str) -> str:
    """Resolve a configured working directory relative to the project root."""
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return str(candidate.resolve())


def _resolve_path(value: object) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, (str, Path)):
        raise TypeError(f"expected str or Path, got {type(value).__name__}")
    return Path(value).expanduser().resolve()

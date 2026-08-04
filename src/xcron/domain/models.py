"""Domain model definitions for xcron manifests and normalized state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Tuple


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


@dataclass(frozen=True)
class ProjectConfig:
    """Project-scoped metadata loaded from a selected schedule manifest."""

    id: str


@dataclass(frozen=True)
class DefaultsConfig:
    """Manifest defaults merged into job definitions during normalization."""

    working_dir: str = DEFAULT_WORKING_DIR
    shell: str = DEFAULT_SHELL
    timezone: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScheduleDefinition:
    """Raw schedule definition from the manifest."""

    kind: ScheduleKind
    value: str


@dataclass(frozen=True)
class JobDefinition:
    """Raw job definition from the manifest."""

    id: str
    command: str
    schedule: ScheduleDefinition
    description: str | None = None
    enabled: bool = True
    working_dir: str | None = None
    shell: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    overlap: OverlapPolicy = OverlapPolicy.ALLOW


@dataclass(frozen=True)
class ProjectManifest:
    """Complete raw manifest model before normalization."""

    version: int
    project: ProjectConfig
    jobs: Tuple[JobDefinition, ...]
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)


@dataclass(frozen=True)
class NormalizedExecutionConfig:
    """Resolved execution settings for a single job."""

    command: str
    working_dir: str
    shell: str
    timezone: str | None
    env: Tuple[Tuple[str, str], ...]
    overlap: OverlapPolicy


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class NormalizedManifest:
    """Project-scoped normalized manifest."""

    version: int
    project_id: str
    project_root: str
    manifest_path: str
    jobs: Tuple[NormalizedJob, ...]


def stable_env_items(env: Mapping[str, str]) -> Tuple[Tuple[str, str], ...]:
    """Return a stable, sorted representation of environment mappings."""
    return tuple(sorted((str(key), str(value)) for key, value in env.items()))


def build_qualified_job_id(project_id: str, job_id: str) -> str:
    """Build the backend-neutral fully-qualified job identity."""
    return f"{project_id}.{job_id}"


def build_artifact_id(project_id: str, job_id: str) -> str:
    """Build a filesystem and scheduler-friendly identifier."""
    qualified_id = build_qualified_job_id(project_id, job_id)
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in qualified_id)


def resolve_working_dir(project_root: Path, value: str) -> str:
    """Resolve a configured working directory relative to the project root."""
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return str(candidate.resolve())

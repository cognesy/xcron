"""Public value types and failures of the workspace module.

A workspace is the directory an xcron invocation is scoped to, plus the
machine-local state root its derived artifacts land in. Everything callers can
observe about that — the resolved layouts, the identity marker, and the typed
failures — is here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(Exception):
    """Base exception for workspace identity and layout problems."""


class WorkspaceResolutionError(WorkspaceError):
    """Raised when the requested workspace root is missing or is not a directory."""


class UnsupportedPlatformError(WorkspaceError):
    """Raised when the host platform has no defined xcron state root."""


class WorkspaceMarkerError(WorkspaceError):
    """Base exception for a marker file that exists but cannot be trusted.

    A *missing* marker is deliberately not one of these. For one release a
    directory that looks like a workspace but carries no marker is accepted
    with a warning, so that adopting the marker does not break every existing
    installation on the day it ships.
    """


class MalformedMarkerError(WorkspaceMarkerError):
    """Raised when `marker.toml` is unreadable, unparseable, or the wrong shape."""


class UnsupportedMarkerSchemaError(WorkspaceMarkerError):
    """Raised when `marker.toml` declares a schema this build does not understand."""


@dataclass(frozen=True)
class WorkspaceMarker:
    """The contents of a workspace's `marker.toml`.

    The marker states that a directory is an xcron workspace on purpose, rather
    than by accidentally containing a `schedules/` folder. Its `schema` is the
    compatibility handle: a future layout change bumps it, and an older build
    refuses rather than guessing at a layout it cannot read.
    """

    kind: str
    schema: int
    created_by: str


@dataclass(frozen=True)
class ProjectWorkspace:
    """One resolved workspace: what it is, and where its own files live.

    `marker` is ``None`` when the directory qualified by layout alone.
    `config_path` names the workspace configuration layer whether or not the
    file exists — what an absent file means is the configuration module's
    decision, not this one's.
    """

    root: Path
    manifest_dir: Path
    config_path: Path
    marker_path: Path
    marker: WorkspaceMarker | None

    @property
    def is_marked(self) -> bool:
        return self.marker is not None


@dataclass(frozen=True)
class XcronHome:
    """The layout of the per-user xcron home directory."""

    root: Path
    schedules_dir: Path
    manifest_path: Path
    metrics_path: Path
    marker_path: Path


@dataclass(frozen=True)
class WorkspaceInitResult:
    """What one idempotent initialization run actually changed.

    Init reports rather than asserts. `created_paths` names paths this run
    brought into existence, `retained_paths` names paths it found and left
    alone, `migrated_paths` names legacy locations it adopted in place, and
    `conflicts` names things occupying a needed path that are not what xcron
    expects. Nothing is overwritten or deleted, so a conflict is reported and
    left for a human to resolve.
    """

    xcron_home: str
    schedules_dir: str
    manifest_path: str
    marker_path: str
    created: bool
    created_paths: tuple[str, ...]
    retained_paths: tuple[str, ...]
    migrated_paths: tuple[str, ...]
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
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


__all__ = [
    "MalformedMarkerError",
    "ProjectWorkspace",
    "RuntimePaths",
    "UnsupportedMarkerSchemaError",
    "UnsupportedPlatformError",
    "WorkspaceError",
    "WorkspaceInitResult",
    "WorkspaceMarker",
    "WorkspaceMarkerError",
    "WorkspaceResolutionError",
    "XcronHome",
]

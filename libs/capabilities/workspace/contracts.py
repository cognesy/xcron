"""Public value types and failures of the workspace module.

A workspace is the directory an xcron invocation is scoped to, plus the
machine-local state root its derived artifacts land in. Everything callers can
observe about that — the resolved paths and the one typed failure — is here.
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
    "RuntimePaths",
    "UnsupportedPlatformError",
    "WorkspaceError",
    "WorkspaceResolutionError",
]

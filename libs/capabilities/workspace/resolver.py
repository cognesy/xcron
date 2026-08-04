"""Which directory an invocation is scoped to, and where xcron's home is."""

from __future__ import annotations

import os
from pathlib import Path

from xcron_libs.capabilities.workspace.contracts import WorkspaceResolutionError

XCRON_HOME_ENV_VAR = "XCRON_HOME"
MANIFEST_DIR = Path("schedules")
_LEGACY_MANIFEST_ROOT = "resource" + "s"
LEGACY_MANIFEST_DIR = Path(_LEGACY_MANIFEST_ROOT) / MANIFEST_DIR


def resolve_xcron_home(env: dict[str, str] | None = None) -> Path:
    """Return the xcron home directory (~/.xcron by default, XCRON_HOME override)."""
    env_map = os.environ if env is None else env
    override = env_map.get(XCRON_HOME_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".xcron").resolve()


def _has_schedules(directory: Path) -> bool:
    """Check whether a directory contains a current or legacy schedule dir."""
    return (directory / MANIFEST_DIR).is_dir() or (directory / LEGACY_MANIFEST_DIR).is_dir()


def resolve_project_root(project_path: str | Path | None = None) -> Path:
    """Resolve the target project root.

    Priority: explicit --project > cwd (if it has schedules/) > ~/.xcron
    """
    if project_path is not None:
        candidate = Path(project_path).expanduser()
    else:
        cwd = Path.cwd()
        candidate = cwd if _has_schedules(cwd) else resolve_xcron_home()
    resolved = candidate.resolve()
    if not resolved.exists():
        raise WorkspaceResolutionError(f"project path does not exist: {resolved}")
    if not resolved.is_dir():
        raise WorkspaceResolutionError(f"project path is not a directory: {resolved}")
    return resolved


def resolve_manifest_dir(project_root: Path) -> Path:
    """Resolve the schedules directory for one workspace root."""
    primary = (project_root / MANIFEST_DIR).resolve()
    if primary.exists():
        return primary
    legacy = (project_root / LEGACY_MANIFEST_DIR).resolve()
    if legacy.exists():
        return legacy
    return primary

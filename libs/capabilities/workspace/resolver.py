"""Which directory an invocation is scoped to, and where xcron's home is.

Resolution has one order and it is stated here once:

1. an explicit path — the ``--project`` flag or the SDK argument
2. ``XCRON_PROJECT``
3. the nearest workspace at or above the working directory
4. the xcron home, ``~/.xcron`` or ``XCRON_HOME``
5. otherwise a typed error

Steps 1 and 2 name a directory outright and are taken as given; a caller that
names a directory means that directory, and xcron does not second-guess it by
walking anywhere. Step 3 walks up, so running xcron from a subdirectory of a
workspace behaves the way every other project-scoped tool does.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Mapping

from xcron_libs.capabilities.workspace.contracts import (
    ProjectWorkspace,
    WorkspaceResolutionError,
)
from xcron_libs.capabilities.workspace.marker import (
    MISSING_MARKER_HINT,
    marker_path,
    read_marker,
)
from xcron_libs.shared.observability import get_logger

XCRON_HOME_ENV_VAR = "XCRON_HOME"
XCRON_PROJECT_ENV_VAR = "XCRON_PROJECT"
MANIFEST_DIR = Path("schedules")
_LEGACY_MANIFEST_ROOT = "resource" + "s"
LEGACY_MANIFEST_DIR = Path(_LEGACY_MANIFEST_ROOT) / MANIFEST_DIR

#: Filename of the per-workspace configuration layer.
WORKSPACE_CONFIG_NAME = "config.yaml"


def resolve_xcron_home(env: Mapping[str, str] | None = None) -> Path:
    """Return the xcron home directory (~/.xcron by default, XCRON_HOME override)."""
    env_map = os.environ if env is None else env
    override = env_map.get(XCRON_HOME_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".xcron").resolve()


def _has_schedules(directory: Path) -> bool:
    """Check whether a directory contains a current or legacy schedule dir."""
    return (directory / MANIFEST_DIR).is_dir() or (directory / LEGACY_MANIFEST_DIR).is_dir()


def is_workspace(directory: Path) -> bool:
    """Whether a directory presents as an xcron workspace.

    A marker settles it. Layout alone still counts for one release, so every
    workspace created before the marker existed keeps working.
    """
    return marker_path(directory).is_file() or _has_schedules(directory)


def find_workspace_root(start: Path | None = None) -> Path | None:
    """The nearest workspace at or above `start`, or ``None`` if there is none."""
    current = (Path.cwd() if start is None else Path(start)).expanduser().resolve()
    for directory in (current, *current.parents):
        if is_workspace(directory):
            return directory
    return None


def resolve_project_root(
    project_path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    start: Path | None = None,
) -> Path:
    """Resolve the target workspace root, in the order this module documents."""
    env_map = os.environ if env is None else env
    if project_path is not None:
        candidate = Path(project_path).expanduser()
    else:
        from_env = env_map.get(XCRON_PROJECT_ENV_VAR)
        if from_env:
            candidate = Path(from_env).expanduser()
        else:
            found = find_workspace_root(start)
            candidate = found if found is not None else resolve_xcron_home(env_map)

    resolved = candidate.resolve()
    if not resolved.exists():
        raise WorkspaceResolutionError(
            f"project path does not exist: {resolved}; run `xcron init` to create one"
        )
    if not resolved.is_dir():
        raise WorkspaceResolutionError(f"project path is not a directory: {resolved}")
    return resolved


def resolve_workspace(
    project_path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    start: Path | None = None,
    on_missing_marker: Callable[[Path], None] | None = None,
) -> ProjectWorkspace:
    """Resolve one workspace and everything about it callers may observe.

    An unmarked workspace is reported through `on_missing_marker`, defaulting to
    a structured warning on stderr. A marker that is present but malformed or
    from an unsupported schema raises instead: acting on a statement xcron
    cannot read is worse than acting on no statement at all.
    """
    root = resolve_project_root(project_path, env=env, start=start)
    marker = read_marker(root)
    if marker is None:
        (on_missing_marker or _warn_missing_marker)(root)
    return ProjectWorkspace(
        root=root,
        manifest_dir=resolve_manifest_dir(root),
        config_path=root / WORKSPACE_CONFIG_NAME,
        marker_path=marker_path(root),
        marker=marker,
    )


def _warn_missing_marker(root: Path) -> None:
    # Resolved at call time, not at import: `get_logger` reconfigures logging
    # for the current stderr, and this warning fires before any instrumented
    # action has had the chance to.
    get_logger(__name__).warning(
        "workspace_marker_missing",
        workspace=str(root),
        marker=str(marker_path(root)),
        hint=MISSING_MARKER_HINT,
    )


def resolve_manifest_dir(project_root: Path) -> Path:
    """Resolve the schedules directory for one workspace root."""
    primary = (project_root / MANIFEST_DIR).resolve()
    if primary.exists():
        return primary
    legacy = (project_root / LEGACY_MANIFEST_DIR).resolve()
    if legacy.exists():
        return legacy
    return primary


__all__ = [
    "LEGACY_MANIFEST_DIR",
    "MANIFEST_DIR",
    "WORKSPACE_CONFIG_NAME",
    "XCRON_HOME_ENV_VAR",
    "XCRON_PROJECT_ENV_VAR",
    "find_workspace_root",
    "is_workspace",
    "resolve_manifest_dir",
    "resolve_project_root",
    "resolve_workspace",
    "resolve_xcron_home",
]

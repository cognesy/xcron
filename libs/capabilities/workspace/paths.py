"""Where a workspace's derived artifacts live on this machine.

Only *where* derived state lives is decided here. What is written into it
belongs to the module that owns the file: reconciliation owns
``project-state.json`` and wrapper scripts, operations owns logs and metrics.

Nothing in this module reads the environment. ``XCRON_STATE_ROOT`` is a
setting, and settings are composed once by :mod:`xcron_libs.configuration` and
handed down as a value — a second reader here would be free to disagree with
the one the runtime resolved.
"""

from __future__ import annotations

from pathlib import Path
import sys

from xcron_libs.capabilities.workspace.contracts import (
    RuntimePaths,
    UnsupportedPlatformError,
    XcronHome,
)
from xcron_libs.capabilities.workspace.marker import MARKER_FILENAME
from xcron_libs.capabilities.workspace.resolver import MANIFEST_DIR, resolve_xcron_home
from xcron_libs.domain.models import NormalizedJob

#: The published name of the state-root setting, kept here because this is the
#: module that defines what it means.
STATE_ENV_VAR = "XCRON_STATE_ROOT"

#: Filename of the starter manifest an initialized workspace carries.
DEFAULT_MANIFEST_NAME = "default.yaml"


def resolve_state_root(
    platform: str | None = None,
    home: Path | None = None,
    override: Path | str | None = None,
) -> Path:
    """Resolve the machine-local derived state root for xcron.

    `override` is the composed setting, already resolved by the caller. When it
    is absent the platform default applies.
    """
    if override is not None:
        return Path(override).expanduser().resolve()

    selected_home = Path.home() if home is None else Path(home)
    selected = sys.platform if platform is None else platform
    if selected.startswith(("darwin", "linux")):
        return (selected_home / ".xcron").resolve()
    raise UnsupportedPlatformError(f"unsupported platform for xcron prototype: {selected}")


def xcron_home_layout(root: Path | None = None, *, env: dict[str, str] | None = None) -> XcronHome:
    """The layout of the per-user xcron home.

    One statement of where the home's own files sit, so the metrics store, the
    initializer, and the CLI cannot each derive a slightly different answer.
    """
    home = Path(root).expanduser().resolve() if root is not None else resolve_xcron_home(env)
    schedules_dir = home / MANIFEST_DIR
    return XcronHome(
        root=home,
        schedules_dir=schedules_dir,
        manifest_path=schedules_dir / DEFAULT_MANIFEST_NAME,
        metrics_path=(home / "metrics" / "metrics.json").resolve(),
        marker_path=home / MARKER_FILENAME,
    )


def resolve_project_state_dir(project_id: str, state_root: Path | None = None) -> Path:
    """Resolve the per-project derived state directory."""
    root = resolve_state_root() if state_root is None else Path(state_root).expanduser().resolve()
    return root / "projects" / project_id


def resolve_runtime_paths(job: NormalizedJob, state_root: Path | None = None) -> RuntimePaths:
    """Resolve deterministic managed runtime paths for one job."""
    project_dir = resolve_project_state_dir(job.project_id, state_root=state_root)
    wrappers_dir = project_dir / "wrappers"
    logs_dir = project_dir / "logs"
    locks_dir = project_dir / "locks"
    return RuntimePaths(
        project_dir=project_dir,
        wrappers_dir=wrappers_dir,
        logs_dir=logs_dir,
        locks_dir=locks_dir,
        wrapper_path=wrappers_dir / f"{job.artifact_id}.sh",
        stdout_log_path=logs_dir / f"{job.artifact_id}.out.log",
        stderr_log_path=logs_dir / f"{job.artifact_id}.err.log",
        event_log_path=logs_dir / f"{job.artifact_id}.events.jsonl",
        lock_path=locks_dir / f"{job.artifact_id}.lock",
    )


def ensure_runtime_dirs(paths: RuntimePaths) -> None:
    """Create the managed runtime directories for one job."""
    paths.wrappers_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    paths.locks_dir.mkdir(parents=True, exist_ok=True)


def runtime_log_paths_for_wrapper(wrapper_path: Path) -> tuple[Path, Path]:
    """Derive stdout/stderr log paths from one managed wrapper path."""
    wrappers_dir = wrapper_path.expanduser().resolve().parent
    project_dir = wrappers_dir.parent
    artifact_id = wrapper_path.stem
    logs_dir = project_dir / "logs"
    return logs_dir / f"{artifact_id}.out.log", logs_dir / f"{artifact_id}.err.log"


def runtime_event_log_path_for_wrapper(wrapper_path: Path) -> Path:
    """Derive the JSONL wrapper event log path from one managed wrapper path."""
    wrappers_dir = wrapper_path.expanduser().resolve().parent
    project_dir = wrappers_dir.parent
    artifact_id = wrapper_path.stem
    return project_dir / "logs" / f"{artifact_id}.events.jsonl"


__all__ = [
    "DEFAULT_MANIFEST_NAME",
    "STATE_ENV_VAR",
    "ensure_runtime_dirs",
    "resolve_project_state_dir",
    "resolve_runtime_paths",
    "resolve_state_root",
    "runtime_event_log_path_for_wrapper",
    "runtime_log_paths_for_wrapper",
    "xcron_home_layout",
]

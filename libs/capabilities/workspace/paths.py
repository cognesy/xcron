"""Where a workspace's derived artifacts live on this machine.

Only *where* derived state lives is decided here. What is written into it
belongs to the module that owns the file: reconciliation owns
``project-state.json`` and wrapper scripts, operations owns logs and metrics.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from xcron_libs.capabilities.workspace.contracts import RuntimePaths, UnsupportedPlatformError
from xcron_libs.domain.models import NormalizedJob

STATE_ENV_VAR = "XCRON_STATE_ROOT"


def resolve_state_root(
    platform: str | None = None,
    home: Path | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    """Resolve the machine-local derived state root for xcron."""
    env_map = os.environ if env is None else env
    override = env_map.get(STATE_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()

    selected_home = Path.home() if home is None else Path(home)
    selected = sys.platform if platform is None else platform
    if selected.startswith(("darwin", "linux")):
        return (selected_home / ".xcron").resolve()
    raise UnsupportedPlatformError(f"unsupported platform for xcron prototype: {selected}")


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

"""Deterministic runtime paths for wrappers, logs, and lock directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from libs.domain.models import NormalizedJob
from libs.services.state_store import resolve_project_state_dir


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
    lock_path: Path


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

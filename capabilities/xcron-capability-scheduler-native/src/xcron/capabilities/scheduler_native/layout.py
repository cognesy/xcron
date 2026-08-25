"""Workspace-owned runtime-path access exposed to the native scheduler."""

from __future__ import annotations

from pathlib import Path

from xcron.contracts import NormalizedJob, RuntimePaths, WorkspacePort


class RuntimeLayout:
    """Adapt only the public workspace port to native scheduler needs."""

    def __init__(self, workspace: WorkspacePort) -> None:
        self._workspace = workspace

    def runtime_paths(self, job: NormalizedJob, *, state_root: Path | None = None) -> RuntimePaths:
        return self._workspace.runtime_paths(job, state_root=state_root)

    def project_state_path(self, project_id: str, *, state_root: Path | None = None) -> Path:
        return self._workspace.project_state_path(project_id, state_root=state_root)


def wrapper_log_paths(wrapper_path: Path) -> tuple[Path, Path]:
    """Read paths from a persisted wrapper location without choosing a layout."""
    project_dir = wrapper_path.expanduser().resolve().parent.parent
    artifact_id = wrapper_path.stem
    logs_dir = project_dir / "logs"
    return logs_dir / f"{artifact_id}.out.log", logs_dir / f"{artifact_id}.err.log"


def wrapper_event_log_path(wrapper_path: Path) -> Path:
    project_dir = wrapper_path.expanduser().resolve().parent.parent
    return project_dir / "logs" / f"{wrapper_path.stem}.events.jsonl"

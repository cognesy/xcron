"""Derived local state storage for xcron-managed project metadata."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from libs.domain.diffing import DeployedJobState, ProjectState


STATE_ENV_VAR = "XCRON_STATE_ROOT"
STATE_FILENAME = "project-state.json"


def default_backend_for_current_platform(platform: str | None = None) -> str:
    """Return the backend xcron should target on the current platform."""
    selected = sys.platform if platform is None else platform
    if selected.startswith("darwin"):
        return "launchd"
    if selected.startswith("linux"):
        return "cron"
    raise ValueError(f"unsupported platform for xcron prototype: {selected}")


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

    selected = sys.platform if platform is None else platform
    selected_home = Path.home() if home is None else Path(home)
    if selected.startswith("darwin"):
        return (selected_home / "Library" / "Application Support" / "xcron").resolve()
    if selected.startswith("linux"):
        return (selected_home / ".local" / "state" / "xcron").resolve()
    raise ValueError(f"unsupported platform for xcron prototype: {selected}")


def resolve_project_state_dir(project_id: str, state_root: Path | None = None) -> Path:
    """Resolve the per-project derived state directory."""
    root = resolve_state_root() if state_root is None else Path(state_root).expanduser().resolve()
    return root / "projects" / project_id


def resolve_project_state_path(project_id: str, state_root: Path | None = None) -> Path:
    """Resolve the JSON file that stores one project's derived deployment metadata."""
    return resolve_project_state_dir(project_id, state_root=state_root) / STATE_FILENAME


def load_project_state(project_id: str, backend: str, state_root: Path | None = None) -> ProjectState:
    """Load one project's derived local state or return an empty baseline."""
    path = resolve_project_state_path(project_id, state_root=state_root)
    if not path.exists():
        return ProjectState(project_id=project_id, backend=backend, manifest_hash=None, jobs=())

    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = tuple(
        DeployedJobState(
            qualified_id=str(item["qualified_id"]),
            job_id=str(item["job_id"]),
            artifact_id=str(item["artifact_id"]),
            backend=str(item["backend"]),
            enabled=bool(item["enabled"]),
            desired_hash=str(item["desired_hash"]),
            definition_hash=item.get("definition_hash"),
            observed_hash=item.get("observed_hash"),
            label=item.get("label"),
            artifact_path=item.get("artifact_path"),
            wrapper_path=item.get("wrapper_path"),
            stdout_log_path=item.get("stdout_log_path"),
            stderr_log_path=item.get("stderr_log_path"),
            last_applied_at=item.get("last_applied_at"),
        )
        for item in data.get("jobs", [])
    )
    return ProjectState(
        project_id=str(data.get("project_id", project_id)),
        backend=str(data.get("backend", backend)),
        manifest_hash=data.get("manifest_hash"),
        jobs=tuple(sorted(jobs, key=lambda job: job.qualified_id)),
        updated_at=data.get("updated_at"),
    )


def save_project_state(state: ProjectState, state_root: Path | None = None) -> Path:
    """Persist one project's derived local state under the managed state root."""
    path = resolve_project_state_path(state.project_id, state_root=state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_id": state.project_id,
        "backend": state.backend,
        "manifest_hash": state.manifest_hash,
        "updated_at": state.updated_at or utc_timestamp(),
        "jobs": [asdict(job) for job in state.jobs],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def delete_project_state(project_id: str, state_root: Path | None = None) -> None:
    """Remove one project's derived local state file if it exists."""
    path = resolve_project_state_path(project_id, state_root=state_root)
    if path.exists():
        path.unlink()


def utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

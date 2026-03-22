"""Prune one project's deployed scheduler artifacts from the selected backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from libs.actions.validate_project import validate_project
from libs.services import get_logger, instrument_action
from libs.services.backends.cron_service import prune_cron_project
from libs.services.backends.launchd_service import prune_launchd_project
from libs.services.state_store import default_backend_for_current_platform, delete_project_state

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class PruneProjectResult:
    """Structured result for the prune use case."""

    valid: bool
    backend: str | None
    project_id: str | None
    removed: tuple[Any, ...] = field(default_factory=tuple)
    error: str | None = None


@instrument_action("prune_project")
def prune_project(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    backend: str | None = None,
    platform: str | None = None,
    state_root: str | Path | None = None,
    launch_agents_dir: str | Path | None = None,
    launchctl_domain: str | None = None,
    crontab_path: str | Path | None = None,
    manage_launchctl: bool = True,
    manage_crontab: bool = True,
) -> PruneProjectResult:
    """Prune one project's managed backend artifacts and derived state."""
    validation = validate_project(project_path, schedule_name=schedule_name)
    if not validation.valid or validation.normalized_manifest is None:
        LOGGER.warning(
            "prune_validation_failed",
            project_root=validation.project_root,
            manifest_path=validation.manifest_path,
            error_count=len(validation.errors),
            warning_count=len(validation.warnings),
        )
        return PruneProjectResult(valid=False, backend=None, project_id=None, error="project validation failed")

    selected_backend = backend or default_backend_for_current_platform(platform=platform)
    project_id = validation.normalized_manifest.project_id

    if selected_backend == "launchd":
        removed = prune_launchd_project(
            project_id,
            launch_agents_dir=Path(launch_agents_dir).expanduser().resolve() if launch_agents_dir is not None else None,
            domain_target=launchctl_domain,
            manage_launchctl=manage_launchctl,
        )
    elif selected_backend == "cron":
        removed = prune_cron_project(
            project_id,
            crontab_path=Path(crontab_path).expanduser().resolve() if crontab_path is not None else None,
            manage_crontab=manage_crontab,
        )
    else:
        raise ValueError(f"unsupported backend for prune: {selected_backend}")

    delete_project_state(project_id, state_root=Path(state_root).expanduser().resolve() if state_root is not None else None)
    LOGGER.info(
        "project_pruned",
        project_id=project_id,
        backend=selected_backend,
        removed_count=len(removed),
    )
    return PruneProjectResult(
        valid=True,
        backend=selected_backend,
        project_id=project_id,
        removed=tuple(removed),
    )

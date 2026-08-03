"""Prune one project's deployed scheduler artifacts from the selected backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xcron_libs.capabilities.reconciliation.contracts import (
    SchedulerInspection,
    SchedulerRuntimeOptions,
)
from xcron_libs.capabilities.reconciliation.scheduler_registry import (
    SchedulerRegistry,
    default_scheduler_registry,
)
from xcron_libs.capabilities.reconciliation.validation import validate_project
from xcron_libs.services.observability import get_logger, instrument_action
from xcron_libs.services.state_store import default_backend_for_current_platform, delete_project_state

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class PruneProjectResult:
    """Structured result for the prune use case."""

    valid: bool
    backend: str | None
    project_id: str | None
    removed: tuple[SchedulerInspection, ...] = field(default_factory=tuple)
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
    scheduler_registry: SchedulerRegistry | None = None,
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
    options = SchedulerRuntimeOptions.create(
        state_root=state_root,
        launch_agents_dir=launch_agents_dir,
        launchctl_domain=launchctl_domain,
        crontab_path=crontab_path,
        manage_launchctl=manage_launchctl,
        manage_crontab=manage_crontab,
    )
    removed = (scheduler_registry or default_scheduler_registry()).require(selected_backend).prune_project(
        project_id,
        options=options,
    )

    delete_project_state(project_id, state_root=options.state_root)
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

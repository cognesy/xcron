"""Job-level manifest management actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from libs.actions.validate_project import ValidateProjectResult, validate_project
from libs.domain import NormalizedJob, NormalizedManifest, normalize_manifest
from libs.services import (
    ManifestEditError,
    ManifestEditValidationError,
    ValidationMessage,
    add_manifest_job,
    get_logger,
    get_manifest_job,
    instrument_action,
    list_manifest_jobs,
    remove_manifest_job,
    set_manifest_job_enabled,
    update_manifest_job,
)


LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class JobActionResult:
    """Structured result for one job-management action."""

    valid: bool
    project_root: str
    manifest_path: str | None
    validation: ValidateProjectResult | None = None
    jobs: tuple[NormalizedJob, ...] = field(default_factory=tuple)
    raw_jobs: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    job: NormalizedJob | None = None
    raw_job: Mapping[str, Any] | None = None
    removed_job_identifier: str | None = None
    warnings: tuple[ValidationMessage, ...] = field(default_factory=tuple)
    error: str | None = None


@instrument_action("list_jobs")
def list_jobs(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> JobActionResult:
    """List normalized jobs from one selected manifest."""
    validation = validate_project(project_path, schedule_name=schedule_name)
    if not validation.valid or validation.normalized_manifest is None:
        return _invalid_result(project_path, validation)

    raw_jobs = list_manifest_jobs(project_path, schedule_name=schedule_name)
    return JobActionResult(
        valid=True,
        project_root=validation.project_root,
        manifest_path=validation.manifest_path,
        validation=validation,
        jobs=validation.normalized_manifest.jobs,
        raw_jobs=raw_jobs,
    )


@instrument_action("show_job")
def show_job(
    job_identifier: str,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> JobActionResult:
    """Show one normalized job from one selected manifest."""
    validation = validate_project(project_path, schedule_name=schedule_name)
    if not validation.valid or validation.normalized_manifest is None:
        return _invalid_result(project_path, validation)

    job = _find_normalized_job(validation.normalized_manifest, job_identifier)
    if job is None:
        return JobActionResult(
            valid=False,
            project_root=validation.project_root,
            manifest_path=validation.manifest_path,
            validation=validation,
            error=f"job not found in manifest: {job_identifier}",
        )

    raw_job = get_manifest_job(job_identifier, project_path, schedule_name=schedule_name)
    return JobActionResult(
        valid=True,
        project_root=validation.project_root,
        manifest_path=validation.manifest_path,
        validation=validation,
        job=job,
        raw_job=raw_job,
    )


@instrument_action("add_job")
def add_job(
    job_data: Mapping[str, Any],
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> JobActionResult:
    """Add one job to the selected manifest."""
    return _mutate_job_manifest(
        project_path,
        schedule_name=schedule_name,
        mutation=lambda: add_manifest_job(job_data, project_path, schedule_name=schedule_name),
        target_identifier=str(job_data.get("id", "")),
    )


@instrument_action("remove_job")
def remove_job(
    job_identifier: str,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> JobActionResult:
    """Remove one job from the selected manifest."""
    return _mutate_job_manifest(
        project_path,
        schedule_name=schedule_name,
        mutation=lambda: remove_manifest_job(job_identifier, project_path, schedule_name=schedule_name),
        removed_job_identifier=job_identifier,
    )


@instrument_action("update_job")
def update_job(
    job_identifier: str,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    updates: Mapping[str, Any] | None = None,
    clear_fields: Sequence[str] = (),
) -> JobActionResult:
    """Update selected fields for one manifest job."""
    return _mutate_job_manifest(
        project_path,
        schedule_name=schedule_name,
        mutation=lambda: update_manifest_job(
            job_identifier,
            updates=updates,
            clear_fields=clear_fields,
            project_path=project_path,
            schedule_name=schedule_name,
        ),
        target_identifier=job_identifier,
    )


@instrument_action("enable_job")
def enable_job(
    job_identifier: str,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> JobActionResult:
    """Enable one manifest job."""
    return _set_job_enabled(job_identifier, True, project_path, schedule_name=schedule_name)


@instrument_action("disable_job")
def disable_job(
    job_identifier: str,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> JobActionResult:
    """Disable one manifest job."""
    return _set_job_enabled(job_identifier, False, project_path, schedule_name=schedule_name)


def _set_job_enabled(
    job_identifier: str,
    enabled: bool,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> JobActionResult:
    return _mutate_job_manifest(
        project_path,
        schedule_name=schedule_name,
        mutation=lambda: set_manifest_job_enabled(
            job_identifier,
            enabled,
            project_path,
            schedule_name=schedule_name,
        ),
        target_identifier=job_identifier,
    )


def _mutate_job_manifest(
    project_path: str | Path | None,
    *,
    schedule_name: str | None,
    mutation: Any,
    target_identifier: str | None = None,
    removed_job_identifier: str | None = None,
) -> JobActionResult:
    try:
        mutation_result = mutation()
    except ManifestEditValidationError as exc:
        LOGGER.warning(
            "job_mutation_validation_failed",
            project_path=str(Path.cwd() if project_path is None else Path(project_path).expanduser()),
            schedule_name=schedule_name,
            error_count=len(exc.errors),
            warning_count=len(exc.warnings),
        )
        return JobActionResult(
            valid=False,
            project_root=str(Path.cwd() if project_path is None else Path(project_path).expanduser().resolve()),
            manifest_path=None,
            warnings=exc.warnings,
            error=str(exc),
        )
    except ManifestEditError as exc:
        LOGGER.warning(
            "job_mutation_failed",
            project_path=str(Path.cwd() if project_path is None else Path(project_path).expanduser()),
            schedule_name=schedule_name,
            error=str(exc),
        )
        return JobActionResult(
            valid=False,
            project_root=str(Path.cwd() if project_path is None else Path(project_path).expanduser().resolve()),
            manifest_path=None,
            error=str(exc),
        )

    normalized_manifest = normalize_manifest(
        mutation_result.manifest,
        mutation_result.project_root,
        mutation_result.manifest_path,
    )
    job = _find_normalized_job(normalized_manifest, target_identifier) if target_identifier else None
    return JobActionResult(
        valid=True,
        project_root=str(mutation_result.project_root),
        manifest_path=str(mutation_result.manifest_path),
        jobs=normalized_manifest.jobs,
        job=job,
        raw_job=mutation_result.job_data,
        warnings=mutation_result.warnings,
        removed_job_identifier=removed_job_identifier,
    )


def _find_normalized_job(manifest: NormalizedManifest, job_identifier: str | None) -> NormalizedJob | None:
    """Find one normalized job by project-local or qualified id."""
    if not job_identifier:
        return None
    for job in manifest.jobs:
        if job.job_id == job_identifier or job.qualified_id == job_identifier:
            return job
    return None


def _invalid_result(project_path: str | Path | None, validation: ValidateProjectResult) -> JobActionResult:
    """Build a failed action result from validation failure."""
    LOGGER.warning(
        "job_action_validation_failed",
        project_root=validation.project_root,
        manifest_path=validation.manifest_path,
        error_count=len(validation.errors),
        warning_count=len(validation.warnings),
    )
    return JobActionResult(
        valid=False,
        project_root=validation.project_root or str(Path.cwd() if project_path is None else Path(project_path).expanduser().resolve()),
        manifest_path=validation.manifest_path,
        validation=validation,
        error="project validation failed",
    )

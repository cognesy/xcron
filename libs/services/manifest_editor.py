"""Manifest editing helpers for xcron job-level CLI operations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, Sequence

import yaml

from libs.domain.models import ProjectManifest
from libs.services.config_loader import LoadedManifestDocument, attach_parsed_manifest, load_project_manifest
from libs.services.observability import get_logger
from libs.services.schema_validator import (
    ValidationMessage,
    split_validation_messages,
    validate_schema,
    validate_semantics,
)


LOGGER = get_logger(__name__)


class ManifestEditError(Exception):
    """Base exception for manifest editing failures."""


class ManifestEditValidationError(ManifestEditError):
    """Raised when a proposed manifest mutation does not validate."""

    def __init__(self, errors: Sequence[ValidationMessage], warnings: Sequence[ValidationMessage] = ()) -> None:
        self.errors = tuple(errors)
        self.warnings = tuple(warnings)
        message = "; ".join(f"{item.path}: {item.message}" for item in self.errors) or "manifest mutation validation failed"
        super().__init__(message)


class ManifestJobNotFoundError(ManifestEditError):
    """Raised when one requested job does not exist in the selected manifest."""


class ManifestJobAlreadyExistsError(ManifestEditError):
    """Raised when one added job collides with an existing manifest job id."""


@dataclass(frozen=True)
class ManifestMutationResult:
    """Structured result for one manifest mutation."""

    project_root: Path
    manifest_path: Path
    manifest: ProjectManifest
    raw_data: Mapping[str, Any]
    job_data: Mapping[str, Any] | None = None
    warnings: tuple[ValidationMessage, ...] = field(default_factory=tuple)


def list_manifest_jobs(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> tuple[Mapping[str, Any], ...]:
    """Return raw job mappings from one selected manifest."""
    document = load_project_manifest(project_path, schedule_name=schedule_name)
    raw_data = _editable_raw_data(document)
    _validated_manifest(raw_data, document.project_root, document.manifest_path)
    return tuple(deepcopy(job) for job in _jobs_list(raw_data))


def get_manifest_job(
    job_identifier: str,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> Mapping[str, Any]:
    """Return one raw job mapping by local or qualified identifier."""
    document = load_project_manifest(project_path, schedule_name=schedule_name)
    raw_data = _editable_raw_data(document)
    _validated_manifest(raw_data, document.project_root, document.manifest_path)
    _, job_data = _find_job(raw_data, job_identifier)
    return deepcopy(job_data)


def add_manifest_job(
    job_data: Mapping[str, Any],
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> ManifestMutationResult:
    """Add one raw job mapping to the selected manifest."""
    def mutate(raw_data: dict[str, Any]) -> Mapping[str, Any]:
        jobs = _jobs_list(raw_data)
        new_job = deepcopy(dict(job_data))
        job_id = str(new_job.get("id", ""))
        if not job_id:
            raise ManifestEditError("job id is required for add")
        if any(str(existing.get("id")) == job_id for existing in jobs):
            raise ManifestJobAlreadyExistsError(f"job already exists in manifest: {job_id}")
        jobs.append(new_job)
        return new_job

    return mutate_manifest(project_path, schedule_name=schedule_name, mutation=mutate)


def remove_manifest_job(
    job_identifier: str,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> ManifestMutationResult:
    """Remove one job mapping from the selected manifest."""
    def mutate(raw_data: dict[str, Any]) -> None:
        job_index, _ = _find_job(raw_data, job_identifier)
        del _jobs_list(raw_data)[job_index]
        return None

    return mutate_manifest(project_path, schedule_name=schedule_name, mutation=mutate)


def update_manifest_job(
    job_identifier: str,
    *,
    updates: Mapping[str, Any] | None = None,
    clear_fields: Sequence[str] = (),
    project_path: str | Path | None = None,
    schedule_name: str | None = None,
) -> ManifestMutationResult:
    """Update selected raw fields for one manifest job."""
    def mutate(raw_data: dict[str, Any]) -> Mapping[str, Any]:
        _, job_data = _find_job(raw_data, job_identifier)
        for field_name in clear_fields:
            job_data.pop(field_name, None)
        for field_name, value in (updates or {}).items():
            job_data[field_name] = deepcopy(value)
        return job_data

    return mutate_manifest(project_path, schedule_name=schedule_name, mutation=mutate)


def set_manifest_job_enabled(
    job_identifier: str,
    enabled: bool,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> ManifestMutationResult:
    """Set enabled state for one manifest job."""
    return update_manifest_job(
        job_identifier,
        updates={"enabled": enabled},
        project_path=project_path,
        schedule_name=schedule_name,
    )


def mutate_manifest(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    mutation: Any,
) -> ManifestMutationResult:
    """Load, mutate, validate, and atomically rewrite one selected manifest."""
    document = load_project_manifest(project_path, schedule_name=schedule_name)
    raw_data = _editable_raw_data(document)
    job_data = mutation(raw_data)
    manifest, warnings = _validated_manifest(raw_data, document.project_root, document.manifest_path)
    _write_manifest_atomically(document.manifest_path, raw_data)
    LOGGER.info(
        "manifest_written",
        manifest_path=str(document.manifest_path),
        project_root=str(document.project_root),
        warning_count=len(warnings),
    )
    return ManifestMutationResult(
        project_root=document.project_root,
        manifest_path=document.manifest_path,
        manifest=manifest,
        raw_data=raw_data,
        job_data=deepcopy(job_data) if job_data is not None else None,
        warnings=warnings,
    )


def _editable_raw_data(document: LoadedManifestDocument) -> dict[str, Any]:
    """Return a deep-copy mutable manifest mapping."""
    return deepcopy(dict(document.raw_data))


def _jobs_list(raw_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the mutable jobs list from one raw manifest mapping."""
    jobs = raw_data.setdefault("jobs", [])
    if not isinstance(jobs, list):
        raise ManifestEditError("manifest jobs must be a list")
    return jobs


def _find_job(raw_data: Mapping[str, Any], job_identifier: str) -> tuple[int, dict[str, Any]]:
    """Find one job by local or qualified identifier."""
    project_id = str((raw_data.get("project") or {}).get("id", ""))
    qualified_id = f"{project_id}.{job_identifier}" if project_id and "." not in job_identifier else job_identifier
    for index, job_data in enumerate(_jobs_list(raw_data)):
        job_id = str(job_data.get("id", ""))
        if job_id == job_identifier or f"{project_id}.{job_id}" == qualified_id:
            return index, job_data
    raise ManifestJobNotFoundError(f"job not found in manifest: {job_identifier}")


def _validated_manifest(
    raw_data: Mapping[str, Any],
    project_root: Path,
    manifest_path: Path,
) -> tuple[ProjectManifest, tuple[ValidationMessage, ...]]:
    """Validate one raw manifest mapping for safe write-back."""
    schema_messages = validate_schema(raw_data)
    schema_errors, schema_warnings = split_validation_messages(schema_messages)
    if schema_errors:
        raise ManifestEditValidationError(schema_errors, schema_warnings)

    parsed_document = attach_parsed_manifest(
        LoadedManifestDocument(
            project_root=project_root,
            manifest_path=manifest_path,
            raw_data=raw_data,
        )
    )
    if parsed_document.manifest is None:
        raise RuntimeError("parsed manifest unexpectedly missing after editing")

    semantic_messages = validate_semantics(parsed_document.manifest, project_root)
    semantic_errors, semantic_warnings = split_validation_messages(semantic_messages)
    warnings = schema_warnings + semantic_warnings
    if semantic_errors:
        raise ManifestEditValidationError(semantic_errors, warnings)
    return parsed_document.manifest, warnings


def _write_manifest_atomically(manifest_path: Path, raw_data: Mapping[str, Any]) -> None:
    """Atomically write one YAML manifest mapping to disk."""
    serialized = yaml.safe_dump(
        raw_data,
        sort_keys=False,
        default_flow_style=False,
    )
    if not serialized.endswith("\n"):
        serialized += "\n"

    with NamedTemporaryFile("w", encoding="utf-8", dir=str(manifest_path.parent), suffix=manifest_path.suffix, delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(serialized)

    os.replace(temp_path, manifest_path)

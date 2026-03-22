"""Validate one project's selected schedule manifest without mutating scheduler state."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from libs.domain import NormalizedManifest, normalize_manifest
from libs.services import get_logger, instrument_action
from libs.services.config_loader import (
    LoadedManifestDocument,
    ManifestLoadError,
    attach_parsed_manifest,
    load_project_manifest,
)
from libs.services.hash_service import ManifestHashes, build_manifest_hashes
from libs.services.schema_validator import (
    ValidationMessage,
    split_validation_messages,
    validate_schema,
    validate_semantics,
)

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class ValidateProjectResult:
    """Structured result for the validate use case."""

    project_root: str
    manifest_path: str | None
    valid: bool
    errors: tuple[ValidationMessage, ...] = field(default_factory=tuple)
    warnings: tuple[ValidationMessage, ...] = field(default_factory=tuple)
    normalized_manifest: NormalizedManifest | None = None
    hashes: ManifestHashes | None = None


@instrument_action("validate_project")
def validate_project(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
) -> ValidateProjectResult:
    """Load, validate, normalize, and hash one project's selected manifest."""
    try:
        document = load_project_manifest(project_path, schedule_name=schedule_name)
    except ManifestLoadError as exc:
        project_root = Path.cwd() if project_path is None else Path(project_path).expanduser()
        LOGGER.warning(
            "manifest_load_failed",
            project_root=str(project_root.resolve()),
            schedule_name=schedule_name,
            error=str(exc),
        )
        return ValidateProjectResult(
            project_root=str(project_root.resolve()),
            manifest_path=None,
            valid=False,
            errors=(ValidationMessage(level="error", path="/", message=str(exc)),),
        )

    schema_messages = validate_schema(document.raw_data)
    schema_errors, schema_warnings = split_validation_messages(schema_messages)
    if schema_errors:
        LOGGER.warning(
            "manifest_schema_invalid",
            project_root=str(document.project_root),
            manifest_path=str(document.manifest_path),
            error_count=len(schema_errors),
            warning_count=len(schema_warnings),
        )
        return build_failed_result(document, schema_errors, schema_warnings)

    parsed_document = attach_parsed_manifest(document)
    if parsed_document.manifest is None:
        raise RuntimeError("parsed manifest unexpectedly missing after parsing")

    semantic_messages = validate_semantics(parsed_document.manifest, parsed_document.project_root)
    semantic_errors, semantic_warnings = split_validation_messages(semantic_messages)
    warnings = schema_warnings + semantic_warnings
    if semantic_errors:
        LOGGER.warning(
            "manifest_semantics_invalid",
            project_root=str(parsed_document.project_root),
            manifest_path=str(parsed_document.manifest_path),
            error_count=len(semantic_errors),
            warning_count=len(warnings),
        )
        return build_failed_result(parsed_document, semantic_errors, warnings)

    normalized_manifest = normalize_manifest(
        parsed_document.manifest,
        parsed_document.project_root,
        parsed_document.manifest_path,
    )
    hashes = build_manifest_hashes(normalized_manifest)
    LOGGER.info(
        "manifest_validated",
        project_root=str(parsed_document.project_root),
        manifest_path=str(parsed_document.manifest_path),
        project_id=normalized_manifest.project_id,
        job_count=len(normalized_manifest.jobs),
        manifest_hash=hashes.manifest_hash,
        warning_count=len(warnings),
    )
    return ValidateProjectResult(
        project_root=str(parsed_document.project_root),
        manifest_path=str(parsed_document.manifest_path),
        valid=True,
        warnings=warnings,
        normalized_manifest=normalized_manifest,
        hashes=hashes,
    )


def build_failed_result(
    document: LoadedManifestDocument,
    errors: tuple[ValidationMessage, ...],
    warnings: tuple[ValidationMessage, ...] = (),
) -> ValidateProjectResult:
    """Return a failed validation result using already loaded manifest metadata."""
    return ValidateProjectResult(
        project_root=str(document.project_root),
        manifest_path=str(document.manifest_path),
        valid=False,
        errors=errors,
        warnings=warnings,
    )

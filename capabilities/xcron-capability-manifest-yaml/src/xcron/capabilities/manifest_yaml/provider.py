"""Installed entry point and YAML-manifest port adapter."""

from __future__ import annotations

from xcron.capabilities.manifest_yaml._editor import (
    add_manifest_job,
    get_manifest_job,
    list_manifest_jobs,
    remove_manifest_job,
    set_manifest_job_enabled,
    update_manifest_job,
)
from xcron.capabilities.manifest_yaml._hashes import build_manifest_hashes
from xcron.capabilities.manifest_yaml._loader import (
    attach_parsed_manifest,
    load_manifest_data,
    parse_project_manifest,
    resolve_manifest_path,
)
from xcron.capabilities.manifest_yaml._normalization import normalize_manifest
from xcron.capabilities.manifest_yaml._schema import (
    split_validation_messages,
    validate_schema,
    validate_semantics,
)
from xcron.contracts import (
    InvocationContext,
    JobCreateRequest,
    JobLookupRequest,
    JobUpdateRequest,
    LoadedManifestDocument,
    ManifestError,
    ManifestMutationResult,
    ManifestPort,
    ManifestHashes,
    NormalizedManifest,
    ProjectRequest,
    ValidationMessage,
    ValidationReport,
)
from xcron.kernel import (
    AssetDeclaration,
    Capability,
    CapabilityDescriptor,
    CapabilityProvides,
    CapabilityRegistration,
)


class YamlManifestProvider:
    """Own YAML schema, semantic validation, hashing, and atomic job edits."""

    def load(self, request: ProjectRequest, context: InvocationContext) -> LoadedManifestDocument:
        workspace = _workspace(context)
        manifest_path = resolve_manifest_path(
            workspace.root,
            schedule_name=request.schedule_name,
            manifest_dir=workspace.manifest_dir,
        )
        return LoadedManifestDocument(
            project_root=workspace.root,
            manifest_path=manifest_path,
            raw_data=load_manifest_data(manifest_path),
        )

    def validate(self, document: LoadedManifestDocument, context: InvocationContext) -> ValidationReport:
        del context
        schema_messages = validate_schema(document.raw_data)
        schema_errors, schema_warnings = split_validation_messages(schema_messages)
        if schema_errors:
            return ValidationReport(valid=False, errors=schema_errors, warnings=schema_warnings)
        try:
            manifest = parse_project_manifest(document.raw_data)
        except (KeyError, TypeError, ValueError) as error:
            return ValidationReport(
                valid=False,
                errors=(ValidationMessage(level="error", path="/", message=str(error)),),
                warnings=schema_warnings,
            )
        semantic_messages = validate_semantics(manifest, document.project_root)
        semantic_errors, semantic_warnings = split_validation_messages(semantic_messages)
        normalized = None
        if not semantic_errors:
            normalized = normalize_manifest(manifest, document.project_root, document.manifest_path)
        return ValidationReport(
            valid=not semantic_errors,
            errors=semantic_errors,
            warnings=schema_warnings + semantic_warnings,
            normalized_manifest=normalized,
        )

    def normalize(self, document: LoadedManifestDocument, context: InvocationContext) -> NormalizedManifest:
        report = self.validate(document, context)
        if not report.valid or report.normalized_manifest is None:
            details = "; ".join(f"{message.path}: {message.message}" for message in report.errors)
            raise ManifestError(details or "manifest cannot be normalized")
        return report.normalized_manifest

    def hashes(self, manifest: NormalizedManifest) -> ManifestHashes:
        return build_manifest_hashes(manifest)

    def list_jobs(
        self,
        request: ProjectRequest,
        context: InvocationContext,
    ) -> tuple[dict[str, object], ...]:
        workspace = _workspace(context)
        return tuple(
            dict(job)
            for job in list_manifest_jobs(
                workspace.root,
                schedule_name=request.schedule_name,
                manifest_dir=workspace.manifest_dir,
            )
        )

    def get_job(self, request: JobLookupRequest, context: InvocationContext) -> dict[str, object]:
        workspace = _workspace(context)
        return dict(
            get_manifest_job(
                request.job_identifier,
                workspace.root,
                schedule_name=request.schedule_name,
                manifest_dir=workspace.manifest_dir,
            )
        )

    def create_job(self, request: JobCreateRequest, context: InvocationContext) -> ManifestMutationResult:
        workspace = _workspace(context)
        return _mutation_result(
            add_manifest_job(
                request.manifest_data(),
                workspace.root,
                schedule_name=context.options.schedule_name,
                manifest_dir=workspace.manifest_dir,
            )
        )

    def remove_job(self, request: JobLookupRequest, context: InvocationContext) -> ManifestMutationResult:
        workspace = _workspace(context)
        return _mutation_result(
            remove_manifest_job(
                request.job_identifier,
                workspace.root,
                schedule_name=request.schedule_name,
                manifest_dir=workspace.manifest_dir,
            )
        )

    def edit(
        self,
        request: JobLookupRequest,
        mutation: JobUpdateRequest,
        context: InvocationContext,
    ) -> ManifestMutationResult:
        workspace = _workspace(context)
        result = update_manifest_job(
            request.job_identifier,
            updates=mutation.manifest_updates(),
            clear_fields=mutation.manifest_clear_fields(),
            project_path=workspace.root,
            schedule_name=request.schedule_name,
            manifest_dir=workspace.manifest_dir,
        )
        return _mutation_result(result)

    def set_job_enabled(
        self,
        request: JobLookupRequest,
        enabled: bool,
        context: InvocationContext,
    ) -> ManifestMutationResult:
        workspace = _workspace(context)
        return _mutation_result(
            set_manifest_job_enabled(
                request.job_identifier,
                enabled,
                workspace.root,
                schedule_name=request.schedule_name,
                manifest_dir=workspace.manifest_dir,
            )
        )


def _workspace(context: InvocationContext):
    if context.workspace is None:
        raise ManifestError("manifest operations require a resolved workspace")
    return context.workspace


def _mutation_result(result: object) -> ManifestMutationResult:
    """Project an editor-private result into the public contract value."""
    return ManifestMutationResult(
        project_root=str(result.project_root),  # type: ignore[attr-defined]
        manifest_path=str(result.manifest_path),  # type: ignore[attr-defined]
        changed=result.changed,  # type: ignore[attr-defined]
        raw_jobs=tuple(result.raw_data.get("jobs", ())),  # type: ignore[attr-defined]
        raw_job=result.job_data,  # type: ignore[attr-defined]
        warnings=result.warnings,  # type: ignore[attr-defined]
    )


DESCRIPTOR = CapabilityDescriptor(
    capability="manifest",
    implementation="yaml",
    version="0.1.4",
    kernel_api=">=1,<2",
    provides=CapabilityProvides(ports=("manifest",), assets=("schedule-schema",)),
    assets=(AssetDeclaration("schedule-schema", "resources/schemas/schedules.schema.yaml"),),
)


def _build(_: object) -> CapabilityRegistration:
    return CapabilityRegistration(
        ports={"manifest": YamlManifestProvider()},
        assets={"schedule-schema": "resources/schemas/schedules.schema.yaml"},
    )


CAPABILITY = Capability(DESCRIPTOR, _build)

assert isinstance(YamlManifestProvider(), ManifestPort)

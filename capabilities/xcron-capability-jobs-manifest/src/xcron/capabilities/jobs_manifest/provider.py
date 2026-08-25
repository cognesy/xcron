"""Installed typed job-management provider backed by the manifest port."""

from __future__ import annotations

from xcron.contracts import (
    InvocationContext,
    JobActionResult,
    JobCreateRequest,
    JobLookupRequest,
    JobManagementPort,
    JobUpdateRequest,
    ManifestError,
    ManifestPort,
    ProjectRequest,
    ScheduleControlPort,
)
from xcron.kernel import (
    Capability,
    CapabilityDescriptor,
    CapabilityProvides,
    CapabilityRegistration,
    CapabilityRequirement,
)


class ManifestJobManager:
    """Compose typed job operations from public manifest and scheduler ports."""

    def __init__(self, manifest: ManifestPort, scheduler: ScheduleControlPort) -> None:
        self._manifest = manifest
        self._scheduler = scheduler

    def list(self, request: ProjectRequest, context: InvocationContext) -> JobActionResult:
        validation = self._validate(request, context)
        if not validation.valid or validation.normalized_manifest is None:
            return _invalid_result(validation)
        try:
            raw_jobs = self._manifest.list_jobs(request, context)
        except ManifestError as error:
            return _error_result(validation, str(error))
        return JobActionResult(
            valid=True,
            project_root=validation.project_root,
            manifest_path=validation.manifest_path,
            validation=validation,
            jobs=validation.normalized_manifest.jobs,
            raw_jobs=raw_jobs,
        )

    def show(self, request: JobLookupRequest, context: InvocationContext) -> JobActionResult:
        validation = self._validate(request, context)
        if not validation.valid or validation.normalized_manifest is None:
            return _invalid_result(validation)
        job = _normalized_job(validation.normalized_manifest.jobs, request.job_identifier)
        if job is None:
            return _error_result(validation, f"job not found in manifest: {request.job_identifier}")
        try:
            raw_job = self._manifest.get_job(request, context)
        except ManifestError as error:
            return _error_result(validation, str(error))
        return JobActionResult(
            valid=True,
            project_root=validation.project_root,
            manifest_path=validation.manifest_path,
            validation=validation,
            job=job,
            raw_job=raw_job,
        )

    def create(self, request: JobCreateRequest, context: InvocationContext) -> JobActionResult:
        project = ProjectRequest(schedule_name=context.options.schedule_name)
        validation = self._validate(project, context)
        if not validation.valid:
            return _invalid_result(validation)
        try:
            mutation = self._manifest.create_job(request, context)
        except ManifestError as error:
            return _error_result(validation, str(error))
        return self._mutation_result(
            project,
            context,
            validation=validation,
            target_identifier=request.job_id,
            mutation=mutation,
        )

    def update(
        self,
        request: JobLookupRequest,
        mutation: JobUpdateRequest,
        context: InvocationContext,
    ) -> JobActionResult:
        validation = self._validate(request, context)
        if not validation.valid:
            return _invalid_result(validation)
        try:
            result = self._manifest.edit(request, mutation, context)
        except ManifestError as error:
            return _error_result(validation, str(error))
        return self._mutation_result(
            request,
            context,
            validation=validation,
            target_identifier=request.job_identifier,
            mutation=result,
        )

    def enable(self, request: JobLookupRequest, context: InvocationContext) -> JobActionResult:
        return self._set_enabled(request, True, context)

    def disable(self, request: JobLookupRequest, context: InvocationContext) -> JobActionResult:
        return self._set_enabled(request, False, context)

    def remove(self, request: JobLookupRequest, context: InvocationContext) -> JobActionResult:
        validation = self._validate(request, context)
        if not validation.valid:
            return _invalid_result(validation)
        try:
            mutation = self._manifest.remove_job(request, context)
        except ManifestError as error:
            return _error_result(validation, str(error))
        return self._mutation_result(
            request,
            context,
            validation=validation,
            removed_job_identifier=request.job_identifier,
            mutation=mutation,
        )

    def _set_enabled(
        self,
        request: JobLookupRequest,
        enabled: bool,
        context: InvocationContext,
    ) -> JobActionResult:
        validation = self._validate(request, context)
        if not validation.valid:
            return _invalid_result(validation)
        try:
            mutation = self._manifest.set_job_enabled(request, enabled, context)
        except ManifestError as error:
            return _error_result(validation, str(error))
        return self._mutation_result(
            request,
            context,
            validation=validation,
            target_identifier=request.job_identifier,
            mutation=mutation,
        )

    def _validate(self, request: ProjectRequest, context: InvocationContext):
        return self._scheduler.validate(
            ProjectRequest(schedule_name=request.schedule_name),
            context,
        )

    def _mutation_result(
        self,
        request: ProjectRequest,
        context: InvocationContext,
        *,
        validation,
        mutation,
        target_identifier: str | None = None,
        removed_job_identifier: str | None = None,
    ) -> JobActionResult:
        try:
            document = self._manifest.load(ProjectRequest(schedule_name=request.schedule_name), context)
            manifest = self._manifest.normalize(document, context)
        except ManifestError as error:
            return _error_result(validation, str(error))
        job = _normalized_job(manifest.jobs, target_identifier)
        return JobActionResult(
            valid=True,
            project_root=mutation.project_root,
            manifest_path=mutation.manifest_path,
            validation=validation,
            jobs=manifest.jobs,
            raw_jobs=mutation.raw_jobs,
            job=job,
            raw_job=mutation.raw_job,
            removed_job_identifier=removed_job_identifier,
            changed=mutation.changed,
            warnings=mutation.warnings,
        )


def _normalized_job(jobs, identifier: str | None):
    if identifier is None:
        return None
    return next((job for job in jobs if job.job_id == identifier or job.qualified_id == identifier), None)


def _invalid_result(validation) -> JobActionResult:
    return JobActionResult(
        valid=False,
        project_root=validation.project_root,
        manifest_path=validation.manifest_path,
        validation=validation,
        error="project validation failed",
    )


def _error_result(validation, error: str) -> JobActionResult:
    return JobActionResult(
        valid=False,
        project_root=validation.project_root,
        manifest_path=validation.manifest_path,
        validation=validation,
        error=error,
    )


DESCRIPTOR = CapabilityDescriptor(
    capability="jobs",
    implementation="manifest",
    version="0.1.0",
    kernel_api=">=1,<2",
    requires=(CapabilityRequirement("manifest"), CapabilityRequirement("scheduler")),
    provides=CapabilityProvides(ports=("jobs",), cli_paths=("jobs",)),
)


def _build(host) -> CapabilityRegistration:
    return CapabilityRegistration(
        ports={
            "jobs": ManifestJobManager(
                host.require("manifest", ManifestPort),
                host.require("scheduler", ScheduleControlPort),
            )
        },
        cli_paths={"jobs": None},
    )


CAPABILITY = Capability(DESCRIPTOR, _build)

assert isinstance(ManifestJobManager.__new__(ManifestJobManager), JobManagementPort)

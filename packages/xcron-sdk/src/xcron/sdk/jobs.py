"""Typed manifest job-management API."""

from __future__ import annotations

from collections.abc import Callable

from xcron.contracts import (
    InvocationContext,
    JobActionResult,
    JobCreateRequest,
    JobLookupRequest,
    JobManagementPort,
    JobUpdateRequest,
    ProjectRequest,
)


class JobsAPI:
    """Read and edit the selected schedule manifest; reconciliation stays explicit."""

    def __init__(
        self,
        jobs: JobManagementPort,
        context: InvocationContext,
        guard: Callable[[], None],
    ) -> None:
        self._jobs = jobs
        self._context = context
        self._guard = guard

    def list(self) -> JobActionResult:
        self._guard()
        return self._jobs.list(_project(self._context), self._context)

    def show(self, job_identifier: str) -> JobActionResult:
        self._guard()
        return self._jobs.show(_job_lookup(self._context, job_identifier), self._context)

    def add(self, request: JobCreateRequest) -> JobActionResult:
        """Add one typed job definition to the selected manifest."""
        self._guard()
        return self._jobs.create(request, self._context)

    def update(self, job_identifier: str, request: JobUpdateRequest) -> JobActionResult:
        """Apply one typed mutation request to an existing manifest job."""
        self._guard()
        return self._jobs.update(_job_lookup(self._context, job_identifier), request, self._context)

    def enable(self, job_identifier: str) -> JobActionResult:
        self._guard()
        return self._jobs.enable(_job_lookup(self._context, job_identifier), self._context)

    def disable(self, job_identifier: str) -> JobActionResult:
        self._guard()
        return self._jobs.disable(_job_lookup(self._context, job_identifier), self._context)

    def remove(self, job_identifier: str) -> JobActionResult:
        self._guard()
        return self._jobs.remove(_job_lookup(self._context, job_identifier), self._context)


def _project(context: InvocationContext) -> ProjectRequest:
    return ProjectRequest(
        project_path=context.options.project_path,
        schedule_name=context.options.schedule_name,
    )


def _job_lookup(context: InvocationContext, job_identifier: str) -> JobLookupRequest:
    return JobLookupRequest(**_project(context).model_dump(), job_identifier=job_identifier)

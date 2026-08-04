"""Typed manifest job-management API."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from xcron.capabilities.jobs.api import (
    add_job,
    disable_job,
    enable_job,
    list_jobs,
    remove_job,
    show_job,
    update_job,
)
from xcron.capabilities.jobs.contracts import JobActionResult
from xcron.sdk.options import XcronOptions


class JobsAPI:
    """Read and edit the selected schedule manifest; reconciliation stays explicit."""

    def __init__(self, options: XcronOptions, guard: Callable[[], None]) -> None:
        self._options = options
        self._guard = guard

    def list(self) -> JobActionResult:
        self._guard()
        return list_jobs(self._options.project_path, schedule_name=self._options.schedule_name)

    def show(self, job_identifier: str) -> JobActionResult:
        self._guard()
        return show_job(
            job_identifier,
            self._options.project_path,
            schedule_name=self._options.schedule_name,
        )

    def add(self, job_data: Mapping[str, Any]) -> JobActionResult:
        self._guard()
        return add_job(job_data, self._options.project_path, schedule_name=self._options.schedule_name)

    def update(
        self,
        job_identifier: str,
        *,
        updates: Mapping[str, Any] | None = None,
        clear_fields: Sequence[str] = (),
    ) -> JobActionResult:
        self._guard()
        return update_job(
            job_identifier,
            self._options.project_path,
            schedule_name=self._options.schedule_name,
            updates=updates,
            clear_fields=clear_fields,
        )

    def enable(self, job_identifier: str) -> JobActionResult:
        self._guard()
        return enable_job(
            job_identifier,
            self._options.project_path,
            schedule_name=self._options.schedule_name,
        )

    def disable(self, job_identifier: str) -> JobActionResult:
        self._guard()
        return disable_job(
            job_identifier,
            self._options.project_path,
            schedule_name=self._options.schedule_name,
        )

    def remove(self, job_identifier: str) -> JobActionResult:
        self._guard()
        return remove_job(
            job_identifier,
            self._options.project_path,
            schedule_name=self._options.schedule_name,
        )

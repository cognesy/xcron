"""Typed logs and metrics API."""

from __future__ import annotations

from typing import Callable

from xcron_libs.capabilities.operations.api import (
    clear_logs,
    list_logs,
    reset_metrics,
    show_metrics,
)
from xcron_libs.capabilities.operations.contracts import (
    LogsClearResult,
    LogsListResult,
    MetricsResetResult,
    MetricsResult,
)
from xcron_libs.sdk.options import XcronOptions


class OperationsAPI:
    """Inspect runtime evidence and persisted metrics without CLI projections."""

    def __init__(self, options: XcronOptions, guard: Callable[[], None]) -> None:
        self._options = options
        self._guard = guard

    def list_logs(self, *, job_filter: str | None = None) -> LogsListResult:
        self._guard()
        return list_logs(
            self._options.project_path,
            schedule_name=self._options.schedule_name,
            job_filter=job_filter,
            state_root=self._options.state_root,
        )

    def clear_logs(
        self, *, job_filter: str | None = None, dry_run: bool = True
    ) -> LogsClearResult:
        self._guard()
        return clear_logs(
            self._options.project_path,
            schedule_name=self._options.schedule_name,
            job_filter=job_filter,
            state_root=self._options.state_root,
            dry_run=dry_run,
        )

    def show_metrics(self) -> MetricsResult:
        self._guard()
        return show_metrics()

    def reset_metrics(self) -> MetricsResetResult:
        self._guard()
        return reset_metrics()

"""Typed logs and metrics API."""

from __future__ import annotations

from collections.abc import Callable

from xcron.contracts import (
    InvocationContext,
    LogPort,
    LogsClearResult,
    LogsListResult,
    LogsRequest,
    MetricsPort,
    MetricsResetResult,
    MetricsResult,
)


class OperationsAPI:
    """Inspect runtime evidence and persisted metrics without CLI projections."""

    def __init__(
        self,
        logs: LogPort,
        metrics: MetricsPort,
        context: InvocationContext,
        guard: Callable[[], None],
    ) -> None:
        self._logs = logs
        self._metrics = metrics
        self._context = context
        self._guard = guard

    def list_logs(self, *, job_filter: str | None = None) -> LogsListResult:
        self._guard()
        return self._logs.list(_logs_request(self._context, job_filter=job_filter), self._context)

    def clear_logs(self, *, job_filter: str | None = None, dry_run: bool = True) -> LogsClearResult:
        self._guard()
        return self._logs.clear(
            _logs_request(self._context, job_filter=job_filter, dry_run=dry_run),
            self._context,
        )

    def show_metrics(self) -> MetricsResult:
        self._guard()
        return self._metrics.show(self._context)

    def reset_metrics(self) -> MetricsResetResult:
        self._guard()
        return self._metrics.reset(self._context)


def _logs_request(
    context: InvocationContext,
    *,
    job_filter: str | None,
    dry_run: bool = True,
) -> LogsRequest:
    return LogsRequest(
        project_path=context.options.project_path,
        schedule_name=context.options.schedule_name,
        job_filter=job_filter,
        dry_run=dry_run,
    )

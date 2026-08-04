"""Public contracts owned by the runtime operations module.

This module is one of the two entry points outside code may import; the other
is :mod:`xcron.capabilities.operations.api`. It owns the log-inventory and
metrics-snapshot values the module's public API returns.

Nothing here depends on a channel, renderer, or CLI response type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from xcron.capabilities.reconciliation.contracts import ValidateProjectResult


@dataclass(frozen=True)
class LogFileEntry:
    """One discovered log file on disk."""

    qualified_id: str
    kind: str  # "stdout", "stderr", or "events"
    path: str
    size_bytes: int


@dataclass(frozen=True)
class LogsListResult:
    """Structured result for the logs list use case."""

    valid: bool
    project_id: str | None = None
    logs_dir: str | None = None
    files: tuple[LogFileEntry, ...] = field(default_factory=tuple)
    validation: ValidateProjectResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class LogsClearResult:
    """Structured result for the logs clear use case."""

    valid: bool
    project_id: str | None = None
    dry_run: bool = True
    files: tuple[LogFileEntry, ...] = field(default_factory=tuple)
    cleared: int = 0
    validation: ValidateProjectResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class MetricsResult:
    """Channel-neutral snapshot of persisted runtime metrics."""

    path: str
    version: int
    created_at: str
    updated_at: str
    counters: Mapping[str, int]


@dataclass(frozen=True)
class MetricsResetResult(MetricsResult):
    """Metrics snapshot after reset, including the counters it replaced."""

    previous_counters: Mapping[str, int]

"""Runtime metrics operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from xcron_libs.services.metrics import MetricsService


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


def show_metrics() -> MetricsResult:
    return MetricsResult(**_metrics_values(MetricsService().show()))


def reset_metrics() -> MetricsResetResult:
    payload = MetricsService().reset()
    return MetricsResetResult(
        **_metrics_values(payload),
        previous_counters=_counters(payload.get("previous_counters")),
    )


def _metrics_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": str(payload["path"]),
        "version": int(payload["version"]),
        "created_at": str(payload["created_at"]),
        "updated_at": str(payload["updated_at"]),
        "counters": _counters(payload.get("counters")),
    }


def _counters(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): int(count) for key, count in value.items()}

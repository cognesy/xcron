"""Runtime metrics operations."""

from __future__ import annotations

from typing import Any, Mapping

from xcron.capabilities.operations.contracts import MetricsResetResult, MetricsResult
from xcron.capabilities.operations.metrics_store import MetricsService


def record_outcome(counter: str, amount: int = 1) -> None:
    """Record one operational outcome against the metrics store.

    This is the only public write into the metrics state family. Reconciliation
    reaches it through its `OutcomeRecorder` port so that the module counting
    outcomes and the module producing them stay separable.
    """
    MetricsService().increment(counter, amount)


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

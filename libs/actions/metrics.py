"""Runtime metrics actions."""

from __future__ import annotations

from libs.services import MetricsResetResponse, MetricsResponse, MetricsService


def show_metrics() -> MetricsResponse:
    return MetricsResponse(**MetricsService().show())


def reset_metrics() -> MetricsResetResponse:
    return MetricsResetResponse(**MetricsService().reset())

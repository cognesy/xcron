"""Public callable surface of the runtime operations module.

Outside code imports this module and
:mod:`xcron.capabilities.operations.contracts`, and nothing else below
this package.
"""

from __future__ import annotations

from xcron.capabilities.operations.logs import clear_logs, list_logs
from xcron.capabilities.operations.metrics import (
    record_outcome,
    reset_metrics,
    show_metrics,
)

__all__ = [
    "clear_logs",
    "list_logs",
    "record_outcome",
    "reset_metrics",
    "show_metrics",
]

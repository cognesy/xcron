"""Compatibility imports for the runtime operations capability."""

from xcron_libs.capabilities.operations.api import clear_logs, list_logs
from xcron_libs.capabilities.operations.contracts import (
    LogFileEntry,
    LogsClearResult,
    LogsListResult,
)

__all__ = [
    "LogFileEntry",
    "LogsClearResult",
    "LogsListResult",
    "clear_logs",
    "list_logs",
]

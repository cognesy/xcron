"""Compatibility imports for the runtime operations capability."""

from xcron_libs.capabilities.operations.logs import (
    LogFileEntry,
    LogsClearResult,
    LogsListResult,
    clear_logs,
    list_logs,
)

__all__ = [
    "LogFileEntry",
    "LogsClearResult",
    "LogsListResult",
    "clear_logs",
    "list_logs",
]

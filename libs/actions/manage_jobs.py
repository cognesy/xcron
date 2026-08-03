"""Compatibility imports for the manifest jobs capability."""

from xcron_libs.capabilities.jobs.api import (
    add_job,
    disable_job,
    enable_job,
    list_jobs,
    remove_job,
    show_job,
    update_job,
)
from xcron_libs.capabilities.jobs.contracts import JobActionResult

__all__ = [
    "JobActionResult",
    "add_job",
    "disable_job",
    "enable_job",
    "list_jobs",
    "remove_job",
    "show_job",
    "update_job",
]

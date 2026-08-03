"""Public contracts owned by the manifest job-management module.

This module is one of the two entry points outside code may import; the other
is :mod:`xcron_libs.capabilities.jobs.api`. It owns the result type every
job-management use case returns.

Nothing here depends on a channel, renderer, or CLI response type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from xcron_libs.capabilities.reconciliation.contracts import ValidateProjectResult
from xcron_libs.domain import NormalizedJob
from xcron_libs.services.schema_validator import ValidationMessage


@dataclass(frozen=True)
class JobActionResult:
    """Structured result for one job-management action."""

    valid: bool
    project_root: str
    manifest_path: str | None
    validation: ValidateProjectResult | None = None
    jobs: tuple[NormalizedJob, ...] = field(default_factory=tuple)
    raw_jobs: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    job: NormalizedJob | None = None
    raw_job: Mapping[str, Any] | None = None
    removed_job_identifier: str | None = None
    changed: bool = True
    warnings: tuple[ValidationMessage, ...] = field(default_factory=tuple)
    error: str | None = None

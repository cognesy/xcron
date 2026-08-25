"""Public contracts owned by the manifest job-management module.

This module is one of the two entry points outside code may import; the other
is :mod:`xcron.capabilities.jobs.api`. It owns the result type every
job-management use case returns.

Nothing here depends on a channel, renderer, or CLI response type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xcron.capabilities.reconciliation.contracts import ValidateProjectResult
from xcron.domain import NormalizedJob, OverlapPolicy, ScheduleKind
from xcron.capabilities.manifest.contracts import ValidationMessage


class ScheduleRequest(BaseModel):
    """One scheduler-neutral schedule stated by an SDK caller."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ScheduleKind
    value: str

    @classmethod
    def cron(cls, expression: str) -> ScheduleRequest:
        """Build a cron-expression schedule."""
        return cls(kind=ScheduleKind.CRON, value=expression)

    @classmethod
    def every(cls, interval: str) -> ScheduleRequest:
        """Build a portable interval schedule such as ``"1h"``."""
        return cls(kind=ScheduleKind.EVERY, value=interval)

    def manifest_data(self) -> dict[str, str]:
        """Lower the typed schedule at the manifest boundary."""
        return {self.kind.value: self.value}


class JobCreateRequest(BaseModel):
    """Typed input for :meth:`xcron.sdk.jobs.JobsAPI.add`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    command: str
    schedule: ScheduleRequest
    description: str | None = None
    enabled: bool = True
    working_dir: str | None = None
    shell: str | None = None
    env: Mapping[str, str] = Field(default_factory=dict)
    overlap: OverlapPolicy | None = None

    def manifest_data(self) -> dict[str, object]:
        """Lower the typed request to the YAML payload the manifest owns."""
        data: dict[str, object] = {
            "id": self.job_id,
            "command": self.command,
            "schedule": self.schedule.manifest_data(),
            "enabled": self.enabled,
        }
        if self.description is not None:
            data["description"] = self.description
        if self.working_dir is not None:
            data["working_dir"] = self.working_dir
        if self.shell is not None:
            data["shell"] = self.shell
        if self.env:
            data["env"] = dict(self.env)
        if self.overlap is not None:
            data["overlap"] = self.overlap.value
        return data


class JobUpdateField(str, Enum):
    """An optional job field an SDK caller may explicitly clear."""

    DESCRIPTION = "description"
    WORKING_DIR = "working_dir"
    SHELL = "shell"
    ENV = "env"


class JobUpdateRequest(BaseModel):
    """Typed input for :meth:`xcron.sdk.jobs.JobsAPI.update`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command: str | None = None
    schedule: ScheduleRequest | None = None
    description: str | None = None
    working_dir: str | None = None
    shell: str | None = None
    env: Mapping[str, str] | None = None
    overlap: OverlapPolicy | None = None
    clear_fields: frozenset[JobUpdateField] = Field(default_factory=frozenset)

    @model_validator(mode="after")
    def validate_mutation(self) -> JobUpdateRequest:
        """Reject ambiguous clears and empty mutation requests before IO."""
        field_values = {
            JobUpdateField.DESCRIPTION: self.description,
            JobUpdateField.WORKING_DIR: self.working_dir,
            JobUpdateField.SHELL: self.shell,
            JobUpdateField.ENV: self.env,
        }
        conflicts = [
            field.value
            for field, value in field_values.items()
            if value is not None and field in self.clear_fields
        ]
        if conflicts:
            raise ValueError(f"cannot update and clear the same fields: {', '.join(conflicts)}")
        if not self.has_updates():
            raise ValueError("at least one update field or clear field is required")
        return self

    def has_updates(self) -> bool:
        """Return whether the request changes or clears at least one field."""
        return any(
            value is not None
            for value in (
                self.command,
                self.schedule,
                self.description,
                self.working_dir,
                self.shell,
                self.env,
                self.overlap,
            )
        ) or bool(self.clear_fields)

    def manifest_updates(self) -> dict[str, object]:
        """Lower stated changes to the YAML payload the manifest owns."""
        updates: dict[str, object] = {}
        if self.command is not None:
            updates["command"] = self.command
        if self.schedule is not None:
            updates["schedule"] = self.schedule.manifest_data()
        if self.description is not None:
            updates["description"] = self.description
        if self.working_dir is not None:
            updates["working_dir"] = self.working_dir
        if self.shell is not None:
            updates["shell"] = self.shell
        if self.env is not None:
            updates["env"] = dict(self.env)
        if self.overlap is not None:
            updates["overlap"] = self.overlap.value
        return updates

    def manifest_clear_fields(self) -> tuple[str, ...]:
        """Return the manifest-owned spelling of requested clears."""
        return tuple(field.value for field in JobUpdateField if field in self.clear_fields)


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

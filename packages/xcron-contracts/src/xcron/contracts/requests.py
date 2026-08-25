"""Strict, provider-neutral requests used by the SDK and capability ports."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xcron.contracts.domain import OverlapPolicy, ScheduleKind


class ProjectRequest(BaseModel):
    """Select one project manifest without consulting environment variables."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_path: Path | None = None
    schedule_name: str | None = None


class SchedulerRequest(ProjectRequest):
    """Explicit scheduler selection and mutation controls for one operation."""

    backend: str | None = None
    state_root: Path | None = None
    platform: str | None = None
    launch_agents_dir: Path | None = None
    launchctl_domain: str | None = None
    crontab_path: Path | None = None
    manage_launchctl: bool = True
    manage_crontab: bool = True


class JobLookupRequest(ProjectRequest):
    """Select exactly one job in a project manifest."""

    job_identifier: str


class ScheduleRequest(BaseModel):
    """One scheduler-neutral schedule stated by an SDK caller."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ScheduleKind
    value: str

    @classmethod
    def cron(cls, expression: str) -> ScheduleRequest:
        return cls(kind=ScheduleKind.CRON, value=expression)

    @classmethod
    def every(cls, interval: str) -> ScheduleRequest:
        return cls(kind=ScheduleKind.EVERY, value=interval)

    def manifest_data(self) -> dict[str, str]:
        """Lower the typed schedule only at the YAML boundary."""
        return {self.kind.value: self.value}


class JobCreateRequest(BaseModel):
    """Typed input for creating one manifest job."""

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
        data: dict[str, object] = {
            "id": self.job_id,
            "command": self.command,
            "schedule": self.schedule.manifest_data(),
            "enabled": self.enabled,
        }
        for field in ("description", "working_dir", "shell"):
            value = getattr(self, field)
            if value is not None:
                data[field] = value
        if self.env:
            data["env"] = dict(self.env)
        if self.overlap is not None:
            data["overlap"] = self.overlap.value
        return data


class JobUpdateField(str, Enum):
    """A job field an SDK caller may explicitly clear."""

    DESCRIPTION = "description"
    WORKING_DIR = "working_dir"
    SHELL = "shell"
    ENV = "env"


class JobUpdateRequest(BaseModel):
    """Typed input for a partial manifest job mutation."""

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
        stated = {
            JobUpdateField.DESCRIPTION: self.description,
            JobUpdateField.WORKING_DIR: self.working_dir,
            JobUpdateField.SHELL: self.shell,
            JobUpdateField.ENV: self.env,
        }
        conflicts = [field.value for field, value in stated.items() if value is not None and field in self.clear_fields]
        if conflicts:
            raise ValueError(f"cannot update and clear the same fields: {', '.join(conflicts)}")
        if not self.has_updates():
            raise ValueError("at least one update field or clear field is required")
        return self

    def has_updates(self) -> bool:
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
        updates: dict[str, object] = {}
        if self.command is not None:
            updates["command"] = self.command
        if self.schedule is not None:
            updates["schedule"] = self.schedule.manifest_data()
        for field in ("description", "working_dir", "shell", "env"):
            value = getattr(self, field)
            if value is not None:
                updates[field] = dict(value) if field == "env" else value
        if self.overlap is not None:
            updates["overlap"] = self.overlap.value
        return updates

    def manifest_clear_fields(self) -> tuple[str, ...]:
        return tuple(field.value for field in JobUpdateField if field in self.clear_fields)


class LogsRequest(ProjectRequest):
    """Select owned runtime logs without exposing arbitrary paths."""

    job_filter: str | None = None
    dry_run: bool = True


class HookRequest(ProjectRequest):
    """Select a hook target and optional explicit executable."""

    executable_path: Path | None = None

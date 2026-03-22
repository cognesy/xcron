"""Inspect one managed job for one project."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import plistlib
from typing import Any

from libs.actions.status_project import StatusProjectResult, status_project
from libs.domain import NormalizedJob, StatusEntry
from libs.services import get_logger, instrument_action
from libs.services.backends.cron_service import inspect_cron_project
from libs.services.backends.launchd_service import inspect_launchd_project


LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class InspectField:
    """One structured field shown in inspect output."""

    name: str
    value: str


@dataclass(frozen=True)
class InspectSnippet:
    """One backend-native snippet shown in inspect output."""

    name: str
    content: str


@dataclass(frozen=True)
class InspectJobResult:
    """Structured result for the inspect use case."""

    valid: bool
    backend: str | None
    status: StatusProjectResult
    desired_job: NormalizedJob | None = None
    status_entry: StatusEntry | None = None
    desired_fields: tuple[InspectField, ...] = field(default_factory=tuple)
    deployed_fields: tuple[InspectField, ...] = field(default_factory=tuple)
    snippets: tuple[InspectSnippet, ...] = field(default_factory=tuple)
    inspection: Any | None = None
    error: str | None = None


@instrument_action("inspect_job")
def inspect_job(
    job_identifier: str,
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    backend: str | None = None,
    platform: str | None = None,
    launch_agents_dir: str | Path | None = None,
    launchctl_domain: str | None = None,
    crontab_path: str | Path | None = None,
) -> InspectJobResult:
    """Inspect one desired/deployed job in the selected backend."""
    status = status_project(
        project_path,
        schedule_name=schedule_name,
        backend=backend,
        platform=platform,
        launch_agents_dir=launch_agents_dir,
        launchctl_domain=launchctl_domain,
        crontab_path=crontab_path,
    )
    if not status.valid or status.plan is None:
        LOGGER.warning(
            "inspect_status_failed",
            job_identifier=job_identifier,
            backend=status.backend,
            error_count=len(status.validation.errors),
            warning_count=len(status.validation.warnings),
        )
        return InspectJobResult(valid=False, backend=None, status=status, error="project validation failed")

    desired_job = None
    for job in status.plan.manifest.jobs:
        if job.job_id == job_identifier or job.qualified_id == job_identifier:
            desired_job = job
            break

    target_qualified_id = desired_job.qualified_id if desired_job is not None else job_identifier
    status_entry = next((item for item in status.statuses if item.qualified_id == target_qualified_id), None)
    inspections = status.inspections
    if status.backend == "launchd":
        inspections = inspect_launchd_project(
            status.validation.normalized_manifest.project_id,
            launch_agents_dir=Path(launch_agents_dir).expanduser().resolve() if launch_agents_dir is not None else None,
            domain_target=launchctl_domain,
            include_launchctl_print=True,
        )
    elif status.backend == "cron":
        inspections = inspect_cron_project(
            status.validation.normalized_manifest.project_id,
            crontab_path=Path(crontab_path).expanduser().resolve() if crontab_path is not None else None,
        )

    inspection = None
    for item in inspections:
        qualified_id = getattr(item, "qualified_id", None)
        if qualified_id == job_identifier or qualified_id == target_qualified_id:
            inspection = item
            break

    if desired_job is None and inspection is None:
        LOGGER.warning(
            "inspect_job_not_found",
            job_identifier=job_identifier,
            backend=status.backend,
        )
        return InspectJobResult(
            valid=False,
            backend=status.backend,
            status=status,
            error=f"job not found in desired manifest or deployed backend: {job_identifier}",
        )

    LOGGER.info(
        "job_inspected",
        backend=status.backend,
        job_identifier=job_identifier,
        desired_present=desired_job is not None,
        deployed_present=inspection is not None,
    )
    return InspectJobResult(
        valid=True,
        backend=status.backend,
        status=status,
        desired_job=desired_job,
        status_entry=status_entry,
        desired_fields=build_desired_fields(desired_job, status_entry=status_entry),
        deployed_fields=build_deployed_fields(inspection),
        snippets=build_inspect_snippets(inspection),
        inspection=inspection,
    )


def build_desired_fields(desired_job: NormalizedJob | None, *, status_entry: StatusEntry | None) -> tuple[InspectField, ...]:
    """Build normalized desired-job fields for inspect output."""
    if desired_job is None:
        return tuple()

    fields = [
        InspectField("qualified_id", desired_job.qualified_id),
        InspectField("job_id", desired_job.job_id),
        InspectField("status", status_entry.kind.value if status_entry is not None else "unknown"),
        InspectField("schedule", f"{desired_job.schedule.kind.value}={desired_job.schedule.value}"),
        InspectField("enabled", str(desired_job.enabled)),
        InspectField("command", desired_job.execution.command),
        InspectField("working_dir", desired_job.execution.working_dir),
        InspectField("shell", desired_job.execution.shell),
        InspectField("overlap", desired_job.execution.overlap.value),
    ]
    if desired_job.description:
        fields.append(InspectField("description", desired_job.description))
    if desired_job.execution.timezone is not None:
        fields.append(InspectField("timezone", desired_job.execution.timezone))
    if desired_job.execution.env:
        env_text = ", ".join(f"{key}={value}" for key, value in desired_job.execution.env)
        fields.append(InspectField("env", env_text))
    return tuple(fields)


def build_deployed_fields(inspection: Any | None) -> tuple[InspectField, ...]:
    """Build backend-neutral deployed fields for inspect output."""
    if inspection is None:
        return tuple()

    fields: list[InspectField] = [
        InspectField("qualified_id", str(getattr(inspection, "qualified_id", "unknown"))),
        InspectField("backend_enabled", str(getattr(inspection, "enabled", "n/a"))),
        InspectField("desired_hash", str(getattr(inspection, "desired_hash", "n/a"))),
    ]
    definition_hash = getattr(inspection, "definition_hash", None)
    if definition_hash is not None:
        fields.append(InspectField("definition_hash", str(definition_hash)))
    label = getattr(inspection, "label", None)
    if label is not None:
        fields.append(InspectField("label", str(label)))
    artifact_path = getattr(inspection, "artifact_path", None)
    if artifact_path is None:
        artifact_path = getattr(inspection, "plist_path", None)
    if artifact_path is not None:
        fields.append(InspectField("artifact_path", str(artifact_path)))
    wrapper_path = getattr(inspection, "wrapper_path", None)
    if wrapper_path is not None:
        fields.append(InspectField("wrapper_path", str(wrapper_path)))
    stdout_log_path = getattr(inspection, "stdout_log_path", None)
    if stdout_log_path is not None:
        fields.append(InspectField("stdout_log", str(stdout_log_path)))
    stderr_log_path = getattr(inspection, "stderr_log_path", None)
    if stderr_log_path is not None:
        fields.append(InspectField("stderr_log", str(stderr_log_path)))
    loaded = getattr(inspection, "loaded", None)
    if loaded is not None:
        fields.append(InspectField("loaded", str(loaded)))
    return tuple(fields)


def build_inspect_snippets(inspection: Any | None) -> tuple[InspectSnippet, ...]:
    """Build backend-specific raw snippets for inspect output."""
    if inspection is None:
        return tuple()

    snippets: list[InspectSnippet] = []
    raw_entry = getattr(inspection, "raw_entry", None)
    if raw_entry is not None:
        snippets.append(InspectSnippet("raw_entry", str(raw_entry)))

    raw_plist = getattr(inspection, "raw_plist", None)
    if raw_plist is not None:
        snippets.append(
            InspectSnippet(
                "raw_plist",
                plistlib.dumps(raw_plist, fmt=plistlib.FMT_XML, sort_keys=True).decode("utf-8"),
            )
        )

    launchctl_print = getattr(inspection, "launchctl_print", None)
    if launchctl_print:
        snippets.append(InspectSnippet("launchctl_print", str(launchctl_print)))

    return tuple(snippets)

"""Inspect one managed job for one project."""

from __future__ import annotations

from pathlib import Path
import plistlib

from xcron_libs.capabilities.reconciliation.contracts import (
    InspectField,
    InspectJobResult,
    InspectSnippet,
    SchedulerInspection,
    SchedulerRuntimeOptions,
)
from xcron_libs.capabilities.reconciliation.scheduler_registry import (
    SchedulerRegistry,
    default_scheduler_registry,
)
from xcron_libs.capabilities.reconciliation.status import status_project
from xcron_libs.domain import NormalizedJob, StatusEntry
from xcron_libs.services.observability import get_logger, instrument_action


LOGGER = get_logger(__name__)


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
    scheduler_registry: SchedulerRegistry | None = None,
) -> InspectJobResult:
    """Inspect one desired/deployed job in the selected backend."""
    registry = scheduler_registry or default_scheduler_registry()
    status = status_project(
        project_path,
        schedule_name=schedule_name,
        backend=backend,
        platform=platform,
        launch_agents_dir=launch_agents_dir,
        launchctl_domain=launchctl_domain,
        crontab_path=crontab_path,
        scheduler_registry=registry,
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
    options = SchedulerRuntimeOptions.create(
        launch_agents_dir=launch_agents_dir,
        launchctl_domain=launchctl_domain,
        crontab_path=crontab_path,
    )
    inspections = registry.require(status.backend).inspect_project(
        status.validation.normalized_manifest.project_id,
        options=options,
        include_native_detail=True,
    )

    inspection = None
    for item in inspections:
        qualified_id = item.qualified_id
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


def build_deployed_fields(
    inspection: SchedulerInspection | None,
) -> tuple[InspectField, ...]:
    """Build backend-neutral deployed fields for inspect output."""
    if inspection is None:
        return tuple()

    fields: list[InspectField] = [
        InspectField("qualified_id", inspection.qualified_id),
        InspectField("backend_enabled", str(inspection.enabled)),
        InspectField("desired_hash", str(inspection.desired_hash or "n/a")),
    ]
    definition_hash = inspection.definition_hash
    if definition_hash is not None:
        fields.append(InspectField("definition_hash", str(definition_hash)))
    label = inspection.label
    if label is not None:
        fields.append(InspectField("label", str(label)))
    artifact_path = inspection.artifact_path
    if artifact_path is not None:
        fields.append(InspectField("artifact_path", str(artifact_path)))
    wrapper_path = inspection.wrapper_path
    if wrapper_path is not None:
        fields.append(InspectField("wrapper_path", str(wrapper_path)))
    stdout_log_path = inspection.stdout_log_path
    if stdout_log_path is not None:
        fields.append(InspectField("stdout_log", str(stdout_log_path)))
    stderr_log_path = inspection.stderr_log_path
    if stderr_log_path is not None:
        fields.append(InspectField("stderr_log", str(stderr_log_path)))
    event_log_path = inspection.event_log_path
    if event_log_path is not None:
        fields.append(InspectField("event_log", str(event_log_path)))
    loaded = inspection.loaded
    if loaded is not None:
        fields.append(InspectField("loaded", str(loaded)))
    return tuple(fields)


def build_inspect_snippets(
    inspection: SchedulerInspection | None,
) -> tuple[InspectSnippet, ...]:
    """Build backend-specific raw snippets for inspect output."""
    if inspection is None:
        return tuple()

    snippets: list[InspectSnippet] = []
    raw_entry = inspection.raw_entry
    if raw_entry is not None:
        snippets.append(InspectSnippet("raw_entry", str(raw_entry)))

    raw_plist = inspection.raw_plist
    if raw_plist is not None:
        snippets.append(
            InspectSnippet(
                "raw_plist",
                plistlib.dumps(dict(raw_plist), fmt=plistlib.FMT_XML, sort_keys=True).decode("utf-8"),
            )
        )

    launchctl_print = inspection.launchctl_print
    if launchctl_print:
        snippets.append(InspectSnippet("launchctl_print", str(launchctl_print)))

    return tuple(snippets)

"""Linux cron backend for xcron-managed schedules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from libs.actions.plan_project import PlanProjectResult
from libs.domain import DeployedJobState, NormalizedJob, ProjectState, ScheduleKind
from libs.services.logging_paths import resolve_runtime_paths, runtime_log_paths_for_wrapper
from libs.services.observability import get_logger, run_logged_subprocess
from libs.services.state_store import save_project_state
from libs.services.wrapper_renderer import render_wrapper, write_wrapper


BEGIN_MARKER_PREFIX = "# BEGIN XCRON project="
END_MARKER_PREFIX = "# END XCRON project="
JOB_MARKER_PREFIX = "# XCRON job "
DISABLED_MARKER = "# disabled"
JOB_METADATA_PATTERN = re.compile(
    r"^# XCRON job qualified_id=(?P<qualified_id>\S+) job_id=(?P<job_id>\S+) desired_hash=(?P<desired_hash>\S+) definition_hash=(?P<definition_hash>\S+)$"
)

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class CronInspection:
    """Inspection result for one managed cron job."""

    qualified_id: str
    job_id: str | None
    schedule: str
    artifact_path: str
    wrapper_path: Path
    enabled: bool
    desired_hash: str
    definition_hash: str
    raw_entry: str
    stdout_log_path: Path
    stderr_log_path: Path


def read_crontab(*, crontab_path: Path | None = None) -> str:
    """Read crontab content from a file or the current user crontab."""
    if crontab_path is not None:
        return Path(crontab_path).read_text(encoding="utf-8") if Path(crontab_path).exists() else ""

    result = run_logged_subprocess(
        ["crontab", "-l"],
        event="cron_read_crontab",
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.lower()
        if "no crontab" in stderr:
            return ""
        raise RuntimeError(result.stderr.strip() or "failed to read user crontab")
    return result.stdout


def write_crontab(content: str, *, crontab_path: Path | None = None) -> None:
    """Write crontab content to a file or install it for the current user."""
    if crontab_path is not None:
        Path(crontab_path).write_text(content, encoding="utf-8")
        LOGGER.info("cron_file_written", crontab_path=str(crontab_path), line_count=len(content.splitlines()))
        return

    run_logged_subprocess(
        ["crontab", "-"],
        event="cron_write_crontab",
        check=True,
        input=content,
        capture_output=True,
        text=True,
    )


def render_cron_schedule(job: NormalizedJob) -> str:
    """Render a cron-native schedule string for one normalized job."""
    if job.schedule.kind is ScheduleKind.CRON:
        return job.schedule.value

    amount = int(job.schedule.value[:-1])
    suffix = job.schedule.value[-1]
    if suffix == "m":
        return f"*/{amount} * * * *"
    if suffix == "h":
        return f"0 */{amount} * * *"
    if suffix == "d":
        return f"0 0 */{amount} * *"
    if suffix == "w" and amount == 1:
        return "0 0 * * 0"
    raise ValueError(f"cannot translate portable every schedule to cron: {job.schedule.value}")


def render_cron_block(
    manifest_jobs: tuple[NormalizedJob, ...],
    desired_hashes: dict[str, str],
    definition_hashes: dict[str, str],
    *,
    state_root: Path | None = None,
) -> tuple[str, dict[str, Path]]:
    """Render one project-scoped managed cron block and write wrappers."""
    if not manifest_jobs:
        raise ValueError("cannot render cron block without any jobs")

    project_id = manifest_jobs[0].project_id
    lines = [f"{BEGIN_MARKER_PREFIX}{project_id} backend=cron"]
    wrapper_paths: dict[str, Path] = {}
    for job in manifest_jobs:
        desired_hash = desired_hashes[job.qualified_id]
        definition_hash = definition_hashes[job.qualified_id]
        rendered_wrapper = render_wrapper(job, desired_hash, state_root=state_root)
        wrapper_path = write_wrapper(rendered_wrapper)
        wrapper_paths[job.qualified_id] = wrapper_path

        lines.append(
            f"{JOB_MARKER_PREFIX}qualified_id={job.qualified_id} job_id={job.job_id} desired_hash={desired_hash} definition_hash={definition_hash}"
        )
        schedule = render_cron_schedule(job)
        command = f"{schedule} {wrapper_path}"
        if job.enabled:
            lines.append(command)
        else:
            lines.append(DISABLED_MARKER)
            lines.append(f"# {command}")
    lines.append(f"{END_MARKER_PREFIX}{project_id}")
    LOGGER.info("cron_block_rendered", project_id=project_id, job_count=len(manifest_jobs))
    return "\n".join(lines) + "\n", wrapper_paths


def replace_project_block(content: str, project_id: str, replacement: str | None) -> str:
    """Replace one project's managed block while preserving unmanaged crontab content."""
    lines = content.splitlines()
    begin_marker = f"{BEGIN_MARKER_PREFIX}{project_id}"
    end_marker = f"{END_MARKER_PREFIX}{project_id}"

    start_index = None
    end_index = None
    for index, line in enumerate(lines):
        if line.startswith(begin_marker):
            start_index = index
        if start_index is not None and line.startswith(end_marker):
            end_index = index
            break

    replacement_lines = [] if replacement is None else replacement.rstrip("\n").splitlines()
    if start_index is None or end_index is None:
        new_lines = lines[:]
        if replacement_lines:
            if new_lines and new_lines[-1] != "":
                new_lines.append("")
            new_lines.extend(replacement_lines)
        return "\n".join(new_lines).rstrip() + ("\n" if new_lines or replacement_lines else "")

    new_lines = lines[:start_index] + replacement_lines + lines[end_index + 1 :]
    return "\n".join(new_lines).rstrip() + ("\n" if new_lines else "")


def inspect_cron_project(project_id: str, *, crontab_path: Path | None = None) -> tuple[CronInspection, ...]:
    """Inspect the managed cron entries for one project."""
    content = read_crontab(crontab_path=crontab_path)
    artifact_path = str(crontab_path) if crontab_path is not None else "<user crontab>"
    lines = content.splitlines()
    begin_marker = f"{BEGIN_MARKER_PREFIX}{project_id}"
    end_marker = f"{END_MARKER_PREFIX}{project_id}"

    inside = False
    current_meta: re.Match[str] | None = None
    pending_disabled = False
    inspections = []
    for line in lines:
        if line.startswith(begin_marker):
            inside = True
            current_meta = None
            pending_disabled = False
            continue
        if inside and line.startswith(end_marker):
            break
        if not inside:
            continue
        match = JOB_METADATA_PATTERN.match(line)
        if match:
            current_meta = match
            pending_disabled = False
            continue
        if line == DISABLED_MARKER:
            pending_disabled = True
            continue
        if current_meta is None:
            continue

        is_disabled_entry = pending_disabled and line.startswith("# ")
        cron_line = line[2:] if is_disabled_entry else line
        schedule, wrapper_path = split_cron_entry(cron_line)
        wrapper = Path(wrapper_path)
        stdout_log_path, stderr_log_path = runtime_log_paths_for_wrapper(wrapper)
        inspections.append(
            CronInspection(
                qualified_id=current_meta.group("qualified_id"),
                job_id=current_meta.group("job_id"),
                schedule=schedule,
                artifact_path=artifact_path,
                wrapper_path=wrapper,
                enabled=not is_disabled_entry,
                desired_hash=current_meta.group("desired_hash"),
                definition_hash=current_meta.group("definition_hash"),
                raw_entry=line,
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
            )
        )
        current_meta = None
        pending_disabled = False
    results = tuple(inspections)
    LOGGER.info("cron_project_inspected", project_id=project_id, inspection_count=len(results))
    return results


def split_cron_entry(entry: str) -> tuple[str, str]:
    """Split a rendered cron line into the schedule and wrapper path."""
    parts = entry.split(maxsplit=5)
    if len(parts) != 6:
        raise ValueError(f"invalid managed cron entry: {entry}")
    schedule = " ".join(parts[:5])
    command = parts[5]
    return schedule, command


def collect_cron_project_state(project_id: str, *, crontab_path: Path | None = None) -> ProjectState:
    """Translate the current managed cron block into project state."""
    inspections = inspect_cron_project(project_id, crontab_path=crontab_path)
    jobs = tuple(
        DeployedJobState(
            qualified_id=item.qualified_id,
            job_id=item.job_id or item.qualified_id,
            artifact_id=item.qualified_id,
            backend="cron",
            enabled=item.enabled,
            desired_hash=item.desired_hash,
            definition_hash=item.definition_hash,
            observed_hash=item.desired_hash,
            artifact_path=item.artifact_path,
            wrapper_path=str(item.wrapper_path),
            stdout_log_path=str(item.stdout_log_path),
            stderr_log_path=str(item.stderr_log_path),
        )
        for item in inspections
    )
    state = ProjectState(project_id=project_id, backend="cron", manifest_hash=None, jobs=jobs)
    LOGGER.info("cron_project_state_collected", project_id=project_id, job_count=len(jobs))
    return state


def apply_cron_plan(
    plan_result: PlanProjectResult,
    *,
    state_root: Path | None = None,
    crontab_path: Path | None = None,
    manage_crontab: bool = True,
) -> ProjectState:
    """Apply a project plan to cron and persist derived project state."""
    if not plan_result.valid or plan_result.plan is None:
        raise ValueError("cannot apply invalid plan result to cron")
    if plan_result.backend != "cron":
        raise ValueError(f"cron backend received non-cron plan: {plan_result.backend}")

    manifest = plan_result.plan.manifest
    desired_hashes = plan_result.validation.hashes.job_hashes
    definition_hashes = plan_result.validation.hashes.job_definition_hashes
    current_content = read_crontab(crontab_path=crontab_path) if manage_crontab else ""

    if manifest.jobs:
        block, wrapper_paths = render_cron_block(
            manifest.jobs,
            desired_hashes,
            definition_hashes,
            state_root=state_root,
        )
        new_content = replace_project_block(current_content, manifest.project_id, block)
        if manage_crontab:
            write_crontab(new_content, crontab_path=crontab_path)
    else:
        wrapper_paths = {}
        new_content = replace_project_block(current_content, manifest.project_id, None)
        if manage_crontab:
            write_crontab(new_content, crontab_path=crontab_path)

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    state_jobs = []
    for job in manifest.jobs:
        runtime_paths = resolve_runtime_paths(job, state_root=state_root)
        state_jobs.append(
            DeployedJobState(
                qualified_id=job.qualified_id,
                job_id=job.job_id,
                artifact_id=job.artifact_id,
                backend="cron",
                enabled=job.enabled,
                desired_hash=desired_hashes[job.qualified_id],
                definition_hash=definition_hashes[job.qualified_id],
                observed_hash=desired_hashes[job.qualified_id],
                artifact_path=str(crontab_path) if crontab_path is not None else None,
                wrapper_path=str(wrapper_paths[job.qualified_id]),
                stdout_log_path=str(runtime_paths.stdout_log_path),
                stderr_log_path=str(runtime_paths.stderr_log_path),
                last_applied_at=timestamp,
            )
        )
    state = ProjectState(
        project_id=manifest.project_id,
        backend="cron",
        manifest_hash=plan_result.validation.hashes.manifest_hash,
        jobs=tuple(sorted(state_jobs, key=lambda item: item.qualified_id)),
        updated_at=timestamp,
    )
    save_project_state(state, state_root=state_root)
    LOGGER.info(
        "cron_plan_applied",
        project_id=manifest.project_id,
        change_count=len(plan_result.changes),
        applied_job_count=len(state.jobs),
        manage_crontab=manage_crontab,
    )
    return state


def prune_cron_project(project_id: str, *, crontab_path: Path | None = None, manage_crontab: bool = True) -> tuple[CronInspection, ...]:
    """Remove the managed cron block for one project."""
    inspections = inspect_cron_project(project_id, crontab_path=crontab_path)
    content = read_crontab(crontab_path=crontab_path)
    new_content = replace_project_block(content, project_id, None)
    if manage_crontab:
        write_crontab(new_content, crontab_path=crontab_path)
    for item in inspections:
        item.wrapper_path.unlink(missing_ok=True)
    LOGGER.info("cron_project_pruned", project_id=project_id, removed_count=len(inspections), manage_crontab=manage_crontab)
    return inspections

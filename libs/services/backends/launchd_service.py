"""macOS launchd backend for xcron-managed schedules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
import plistlib
import re
from typing import Any

from libs.actions.plan_project import PlanProjectResult
from libs.domain import DeployedJobState, NormalizedJob, PlanChangeKind, ProjectState, ScheduleKind
from libs.services.logging_paths import resolve_runtime_paths, runtime_log_paths_for_wrapper
from libs.services.observability import check_output_logged, get_logger, run_logged_subprocess
from libs.services.state_store import save_project_state
from libs.services.wrapper_renderer import RenderedWrapper, render_wrapper, write_wrapper


LABEL_PREFIX = "com.xcron"
MINUTE_STEP_PATTERN = re.compile(r"^\*/([1-9][0-9]*)$")

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class LaunchdRenderedJob:
    """Rendered wrapper + plist artifact for one launchd-managed job."""

    job: NormalizedJob
    label: str
    plist_path: Path
    desired_hash: str
    definition_hash: str
    wrapper: RenderedWrapper
    plist_content: bytes


@dataclass(frozen=True)
class LaunchdInspection:
    """Inspection result for one managed launchd job."""

    qualified_id: str
    job_id: str | None
    label: str
    plist_path: Path
    wrapper_path: Path | None
    desired_hash: str | None
    definition_hash: str | None
    enabled: bool
    loaded: bool
    raw_plist: dict[str, Any]
    stdout_log_path: Path | None = None
    stderr_log_path: Path | None = None
    launchctl_print: str | None = None


def resolve_launch_agents_dir(home: Path | None = None) -> Path:
    """Resolve the per-user LaunchAgents directory."""
    selected_home = Path.home() if home is None else Path(home)
    return (selected_home / "Library" / "LaunchAgents").resolve()


def launchd_domain_target(uid: int | None = None) -> str:
    """Return the current GUI domain target for launchctl."""
    selected_uid = check_output_logged(["id", "-u"], event="launchd_resolve_uid", text=True).strip() if uid is None else str(uid)
    return f"gui/{selected_uid}"


def build_launchd_label(job: NormalizedJob) -> str:
    """Build the managed launchd label for one job."""
    return f"{LABEL_PREFIX}.{job.artifact_id}"


def render_launchd_job(
    job: NormalizedJob,
    desired_hash: str,
    definition_hash: str,
    *,
    state_root: Path | None = None,
    launch_agents_dir: Path | None = None,
) -> LaunchdRenderedJob:
    """Render wrapper and plist content for one launchd-managed job."""
    wrapper = render_wrapper(job, desired_hash, state_root=state_root)
    label = build_launchd_label(job)
    agents_dir = resolve_launch_agents_dir() if launch_agents_dir is None else Path(launch_agents_dir).expanduser().resolve()
    plist_path = agents_dir / f"{label}.plist"

    plist_data: dict[str, Any] = {
        "Label": label,
        "ProgramArguments": [str(wrapper.runtime_paths.wrapper_path)],
        "RunAtLoad": False,
        "Disabled": not job.enabled,
        "EnvironmentVariables": {
            "XCRON_PROJECT_ID": job.project_id,
            "XCRON_JOB_ID": job.job_id,
            "XCRON_QUALIFIED_ID": job.qualified_id,
            "XCRON_DESIRED_HASH": desired_hash,
            "XCRON_DEFINITION_HASH": definition_hash,
        },
    }
    plist_data.update(render_launchd_schedule(job))
    plist_content = plistlib.dumps(plist_data, fmt=plistlib.FMT_XML, sort_keys=True)
    return LaunchdRenderedJob(
        job=job,
        label=label,
        plist_path=plist_path,
        desired_hash=desired_hash,
        definition_hash=definition_hash,
        wrapper=wrapper,
        plist_content=plist_content,
    )


def render_launchd_schedule(job: NormalizedJob) -> dict[str, Any]:
    """Translate a normalized schedule into launchd keys."""
    schedule = job.schedule
    if schedule.kind is ScheduleKind.EVERY:
        return {"StartInterval": parse_every_seconds(schedule.value)}

    minute, hour, day, month, weekday = schedule.value.split()
    minute_step_match = MINUTE_STEP_PATTERN.fullmatch(minute)
    if minute_step_match and hour == day == month == weekday == "*":
        return {"StartInterval": int(minute_step_match.group(1)) * 60}

    minute_values = parse_calendar_field(minute, "Minute")
    hour_values = parse_calendar_field(hour, "Hour")
    day_values = parse_calendar_field(day, "Day")
    month_values = parse_calendar_field(month, "Month")
    weekday_values = parse_calendar_field(weekday, "Weekday")
    keys_and_values = [
        ("Minute", minute_values),
        ("Hour", hour_values),
        ("Day", day_values),
        ("Month", month_values),
        ("Weekday", weekday_values),
    ]
    specified = [(key, values) for key, values in keys_and_values if values is not None]
    if not specified:
        return {"StartInterval": 60}

    intervals = []
    for combo in product(*(values for _, values in specified)):
        interval = {key: value for (key, _), value in zip(specified, combo)}
        intervals.append(interval)

    if len(intervals) == 1:
        return {"StartCalendarInterval": intervals[0]}
    return {"StartCalendarInterval": intervals}


def parse_every_seconds(value: str) -> int:
    """Convert a portable `every` string to seconds for launchd."""
    amount = int(value[:-1])
    suffix = value[-1]
    multiplier = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
    }[suffix]
    return amount * multiplier


_CALENDAR_FIELD_BOUNDS: dict[str, tuple[int, int]] = {
    "Minute": (0, 59),
    "Hour": (0, 23),
    "Day": (1, 31),
    "Month": (1, 12),
    "Weekday": (0, 7),  # launchd accepts 0-7; both 0 and 7 are Sunday
}


def parse_calendar_field(field: str, field_name: str) -> list[int] | None:
    """Parse one cron field into explicit integer values for StartCalendarInterval.

    Returns None for a wildcard (*).  Handles all standard cron syntax:
    individual values, comma lists, ranges (M-N), steps (*/S, M/S, M-N/S),
    and any combination of these joined by commas.
    """
    if field == "*":
        return None
    min_val, max_val = _CALENDAR_FIELD_BOUNDS[field_name]
    values: set[int] = set()
    for part in field.split(","):
        if "/" in part:
            range_part, _, step_str = part.partition("/")
            step = int(step_str)
            if range_part == "*":
                start, end = min_val, max_val
            elif "-" in range_part:
                lo, _, hi = range_part.partition("-")
                start, end = int(lo), int(hi)
            else:
                start, end = int(range_part), max_val
            values.update(range(start, end + 1, step))
        elif "-" in part:
            lo, _, hi = part.partition("-")
            values.update(range(int(lo), int(hi) + 1))
        else:
            values.add(int(part))
    return sorted(values)


def write_launchd_job(rendered: LaunchdRenderedJob) -> LaunchdRenderedJob:
    """Write wrapper and plist files to disk."""
    write_wrapper(rendered.wrapper)
    rendered.plist_path.parent.mkdir(parents=True, exist_ok=True)
    rendered.plist_path.write_bytes(rendered.plist_content)
    LOGGER.info(
        "launchd_job_written",
        qualified_id=rendered.job.qualified_id,
        label=rendered.label,
        plist_path=str(rendered.plist_path),
        wrapper_path=str(rendered.wrapper.runtime_paths.wrapper_path),
        stdout_log_path=str(rendered.wrapper.runtime_paths.stdout_log_path),
        stderr_log_path=str(rendered.wrapper.runtime_paths.stderr_log_path),
    )
    return rendered


def apply_launchd_plan(
    plan_result: PlanProjectResult,
    *,
    state_root: Path | None = None,
    launch_agents_dir: Path | None = None,
    domain_target: str | None = None,
    manage_launchctl: bool = True,
) -> ProjectState:
    """Apply a project plan to launchd and persist derived project state."""
    if not plan_result.valid or plan_result.plan is None:
        raise ValueError("cannot apply invalid plan result to launchd")
    if plan_result.backend != "launchd":
        raise ValueError(f"launchd backend received non-launchd plan: {plan_result.backend}")

    selected_domain = launchd_domain_target() if domain_target is None else domain_target
    selected_agents_dir = resolve_launch_agents_dir() if launch_agents_dir is None else Path(launch_agents_dir).expanduser().resolve()

    desired_jobs = {job.qualified_id: job for job in plan_result.plan.manifest.jobs}
    desired_hashes = plan_result.validation.hashes.job_hashes
    desired_definition_hashes = plan_result.validation.hashes.job_definition_hashes
    change_by_id = {change.qualified_id: change for change in plan_result.changes}

    rendered_by_id: dict[str, LaunchdRenderedJob] = {}
    for qualified_id, desired_job in desired_jobs.items():
        change = change_by_id.get(qualified_id)
        if change is None or change.kind is PlanChangeKind.NOOP:
            continue
        rendered = render_launchd_job(
            desired_job,
            desired_hashes[qualified_id],
            desired_definition_hashes[qualified_id],
            state_root=state_root,
            launch_agents_dir=selected_agents_dir,
        )
        rendered_by_id[qualified_id] = write_launchd_job(rendered)

    for change in plan_result.changes:
        label = build_launchd_label(change.desired_job) if change.desired_job is not None else change.deployed_job.label
        if change.kind in (PlanChangeKind.CREATE, PlanChangeKind.UPDATE, PlanChangeKind.DRIFT):
            if manage_launchctl:
                bootout_launchd_service(label, selected_domain, check=False)
                bootstrap_launchd_service(rendered_by_id[change.qualified_id].plist_path, selected_domain)
                enable_launchd_service(label, selected_domain)
        elif change.kind is PlanChangeKind.ENABLE:
            if manage_launchctl:
                bootout_launchd_service(label, selected_domain, check=False)
                if change.qualified_id in rendered_by_id:
                    bootstrap_launchd_service(rendered_by_id[change.qualified_id].plist_path, selected_domain)
                else:
                    rendered = render_launchd_job(
                        desired_jobs[change.qualified_id],
                        desired_hashes[change.qualified_id],
                        desired_definition_hashes[change.qualified_id],
                        state_root=state_root,
                        launch_agents_dir=selected_agents_dir,
                    )
                    rendered_by_id[change.qualified_id] = write_launchd_job(rendered)
                    bootstrap_launchd_service(rendered.plist_path, selected_domain)
                enable_launchd_service(label, selected_domain)
        elif change.kind is PlanChangeKind.DISABLE:
            rendered = rendered_by_id.get(change.qualified_id)
            if rendered is None:
                rendered = render_launchd_job(
                    desired_jobs[change.qualified_id],
                    desired_hashes[change.qualified_id],
                    desired_definition_hashes[change.qualified_id],
                    state_root=state_root,
                    launch_agents_dir=selected_agents_dir,
                )
                rendered_by_id[change.qualified_id] = write_launchd_job(rendered)
            if manage_launchctl:
                bootout_launchd_service(label, selected_domain, check=False)
                bootstrap_launchd_service(rendered.plist_path, selected_domain)
                disable_launchd_service(label, selected_domain)
        elif change.kind is PlanChangeKind.REMOVE:
            deployed = change.deployed_job
            if deployed is not None:
                if manage_launchctl and deployed.label:
                    bootout_launchd_service(deployed.label, selected_domain, check=False)
                if deployed.artifact_path:
                    Path(deployed.artifact_path).unlink(missing_ok=True)
                if deployed.wrapper_path:
                    Path(deployed.wrapper_path).unlink(missing_ok=True)

    state_jobs = []
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for job in plan_result.plan.manifest.jobs:
        rendered = rendered_by_id.get(job.qualified_id)
        runtime_paths = resolve_runtime_paths(job, state_root=state_root)
        plist_path = rendered.plist_path if rendered is not None else selected_agents_dir / f"{build_launchd_label(job)}.plist"
        state_jobs.append(
            DeployedJobState(
                qualified_id=job.qualified_id,
                job_id=job.job_id,
                artifact_id=job.artifact_id,
                backend="launchd",
                enabled=job.enabled,
                desired_hash=desired_hashes[job.qualified_id],
                definition_hash=desired_definition_hashes[job.qualified_id],
                observed_hash=desired_hashes[job.qualified_id],
                label=build_launchd_label(job),
                artifact_path=str(plist_path),
                wrapper_path=str(runtime_paths.wrapper_path),
                stdout_log_path=str(runtime_paths.stdout_log_path),
                stderr_log_path=str(runtime_paths.stderr_log_path),
                last_applied_at=timestamp,
            )
        )

    state = ProjectState(
        project_id=plan_result.plan.manifest.project_id,
        backend="launchd",
        manifest_hash=plan_result.validation.hashes.manifest_hash,
        jobs=tuple(sorted(state_jobs, key=lambda item: item.qualified_id)),
        updated_at=timestamp,
    )
    save_project_state(state, state_root=state_root)
    LOGGER.info(
        "launchd_plan_applied",
        project_id=plan_result.plan.manifest.project_id,
        change_count=len(plan_result.changes),
        applied_job_count=len(state.jobs),
        manage_launchctl=manage_launchctl,
        domain_target=selected_domain,
    )
    return state


def inspect_launchd_project(
    project_id: str,
    *,
    launch_agents_dir: Path | None = None,
    domain_target: str | None = None,
    include_launchctl_print: bool = False,
) -> tuple[LaunchdInspection, ...]:
    """Inspect currently installed xcron-managed launchd jobs for one project."""
    selected_agents_dir = resolve_launch_agents_dir() if launch_agents_dir is None else Path(launch_agents_dir).expanduser().resolve()
    selected_domain = launchd_domain_target() if domain_target is None else domain_target
    disabled_labels = read_disabled_labels(selected_domain)

    inspections = []
    for plist_path in sorted(selected_agents_dir.glob(f"{LABEL_PREFIX}.{project_id}.*.plist")):
        raw_plist = plistlib.loads(plist_path.read_bytes())
        env = dict(raw_plist.get("EnvironmentVariables", {}))
        label = str(raw_plist["Label"])
        qualified_id = env.get("XCRON_QUALIFIED_ID", label.removeprefix(f"{LABEL_PREFIX}."))
        loaded, launchctl_print = read_launchd_service_status(
            label,
            selected_domain,
            include_output=include_launchctl_print,
        )
        wrapper_path = None
        program_arguments = raw_plist.get("ProgramArguments") or []
        if program_arguments:
            wrapper_path = Path(program_arguments[0])
        stdout_log_path = None
        stderr_log_path = None
        if wrapper_path is not None:
            stdout_log_path, stderr_log_path = runtime_log_paths_for_wrapper(wrapper_path)
        inspections.append(
            LaunchdInspection(
                qualified_id=qualified_id,
                job_id=env.get("XCRON_JOB_ID"),
                label=label,
                plist_path=plist_path,
                wrapper_path=wrapper_path,
                desired_hash=env.get("XCRON_DESIRED_HASH"),
                definition_hash=env.get("XCRON_DEFINITION_HASH"),
                enabled=label not in disabled_labels,
                loaded=loaded,
                raw_plist=raw_plist,
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                launchctl_print=launchctl_print,
            )
        )
    results = tuple(inspections)
    LOGGER.info(
        "launchd_project_inspected",
        project_id=project_id,
        inspection_count=len(results),
        domain_target=selected_domain,
    )
    return results


def collect_launchd_project_state(
    project_id: str,
    *,
    launch_agents_dir: Path | None = None,
    domain_target: str | None = None,
) -> ProjectState:
    """Translate installed managed launchd artifacts into project state."""
    inspections = inspect_launchd_project(
        project_id,
        launch_agents_dir=launch_agents_dir,
        domain_target=domain_target,
        include_launchctl_print=False,
    )
    jobs = tuple(
        DeployedJobState(
            qualified_id=item.qualified_id,
            job_id=item.job_id or item.qualified_id,
            artifact_id=item.qualified_id,
            backend="launchd",
            enabled=item.enabled,
            desired_hash=item.desired_hash or "",
            definition_hash=item.definition_hash,
            observed_hash=item.desired_hash,
            label=item.label,
            artifact_path=str(item.plist_path),
            wrapper_path=str(item.wrapper_path) if item.wrapper_path else None,
            stdout_log_path=str(item.stdout_log_path) if item.stdout_log_path else None,
            stderr_log_path=str(item.stderr_log_path) if item.stderr_log_path else None,
        )
        for item in inspections
    )
    state = ProjectState(
        project_id=project_id,
        backend="launchd",
        manifest_hash=None,
        jobs=jobs,
    )
    LOGGER.info("launchd_project_state_collected", project_id=project_id, job_count=len(jobs))
    return state


def prune_launchd_project(
    project_id: str,
    *,
    launch_agents_dir: Path | None = None,
    domain_target: str | None = None,
    manage_launchctl: bool = True,
) -> tuple[LaunchdInspection, ...]:
    """Remove all managed launchd artifacts for one project."""
    selected_domain = launchd_domain_target() if domain_target is None else domain_target
    inspections = inspect_launchd_project(
        project_id,
        launch_agents_dir=launch_agents_dir,
        domain_target=selected_domain,
        include_launchctl_print=False,
    )
    for item in inspections:
        if manage_launchctl:
            bootout_launchd_service(item.label, selected_domain, check=False)
        item.plist_path.unlink(missing_ok=True)
        if item.wrapper_path is not None:
            item.wrapper_path.unlink(missing_ok=True)
    LOGGER.info(
        "launchd_project_pruned",
        project_id=project_id,
        removed_count=len(inspections),
        manage_launchctl=manage_launchctl,
        domain_target=selected_domain,
    )
    return inspections


def bootstrap_launchd_service(plist_path: Path, domain_target: str) -> None:
    """Bootstrap one plist into the target launchd domain."""
    run_logged_subprocess(
        ["launchctl", "bootstrap", domain_target, str(plist_path)],
        event="launchd_bootstrap",
        check=True,
        capture_output=True,
        text=True,
    )


def bootout_launchd_service(label: str, domain_target: str, *, check: bool):
    """Remove one launchd service from the target domain."""
    return run_logged_subprocess(
        ["launchctl", "bootout", f"{domain_target}/{label}"],
        event="launchd_bootout",
        check=check,
        capture_output=True,
        text=True,
    )


def enable_launchd_service(label: str, domain_target: str) -> None:
    """Enable one launchd service."""
    run_logged_subprocess(
        ["launchctl", "enable", f"{domain_target}/{label}"],
        event="launchd_enable",
        check=True,
        capture_output=True,
        text=True,
    )


def disable_launchd_service(label: str, domain_target: str) -> None:
    """Disable one launchd service."""
    run_logged_subprocess(
        ["launchctl", "disable", f"{domain_target}/{label}"],
        event="launchd_disable",
        check=True,
        capture_output=True,
        text=True,
    )


def read_disabled_labels(domain_target: str) -> set[str]:
    """Read the disabled-service list for one launchd domain."""
    result = run_logged_subprocess(
        ["launchctl", "print-disabled", domain_target],
        event="launchd_print_disabled",
        check=True,
        capture_output=True,
        text=True,
    )
    disabled = set()
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith('"'):
            continue
        label, _, status = stripped.partition(" => ")
        if status == "disabled":
            disabled.add(label.strip('"'))
    return disabled


def read_launchd_service_status(label: str, domain_target: str, *, include_output: bool) -> tuple[bool, str | None]:
    """Check whether a launchd service is loaded and optionally return print output."""
    result = run_logged_subprocess(
        ["launchctl", "print", f"{domain_target}/{label}"],
        event="launchd_print",
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout if include_output and result.returncode == 0 else None
    return result.returncode == 0, output

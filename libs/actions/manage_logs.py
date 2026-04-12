"""List, rotate, and clear wrapper logs for one xcron project."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from libs.actions.validate_project import ValidateProjectResult, validate_project
from libs.services import get_logger, instrument_action
from libs.services.logging_paths import resolve_runtime_paths
from libs.services.metrics import MetricsService
from libs.services.state_store import resolve_state_root


LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class LogFileEntry:
    """One discovered log file on disk."""

    qualified_id: str
    kind: str  # "stdout" or "stderr"
    path: str
    size_bytes: int


@dataclass(frozen=True)
class LogsListResult:
    """Structured result for the logs list use case."""

    valid: bool
    project_id: str | None = None
    logs_dir: str | None = None
    files: tuple[LogFileEntry, ...] = field(default_factory=tuple)
    validation: ValidateProjectResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class LogsClearResult:
    """Structured result for the logs clear use case."""

    valid: bool
    project_id: str | None = None
    dry_run: bool = True
    files: tuple[LogFileEntry, ...] = field(default_factory=tuple)
    cleared: int = 0
    validation: ValidateProjectResult | None = None
    error: str | None = None


def _collect_log_files(
    validation: ValidateProjectResult,
    *,
    state_root: Path | None,
    job_filter: str | None,
) -> tuple[str | None, list[LogFileEntry]]:
    """Scan runtime log directory for existing log files."""
    manifest = validation.normalized_manifest
    if manifest is None:
        return None, []

    entries: list[LogFileEntry] = []
    logs_dir: str | None = None

    for job in manifest.jobs:
        if job_filter and job.job_id != job_filter and job.qualified_id != job_filter:
            continue
        paths = resolve_runtime_paths(job, state_root=state_root)
        if logs_dir is None:
            logs_dir = str(paths.logs_dir)

        for kind, log_path in (("stdout", paths.stdout_log_path), ("stderr", paths.stderr_log_path)):
            if log_path.exists():
                entries.append(
                    LogFileEntry(
                        qualified_id=job.qualified_id,
                        kind=kind,
                        path=str(log_path),
                        size_bytes=log_path.stat().st_size,
                    )
                )

    # Also check for orphan logs in the logs dir (files not matching any current job)
    if logs_dir is not None and not job_filter:
        known_paths = {entry.path for entry in entries}
        logs_dir_path = Path(logs_dir)
        if logs_dir_path.is_dir():
            for log_file in sorted(logs_dir_path.glob("*.log")):
                if str(log_file) not in known_paths:
                    stem = log_file.stem
                    if stem.endswith(".out"):
                        kind = "stdout"
                        artifact_id = stem.removesuffix(".out")
                    elif stem.endswith(".err"):
                        kind = "stderr"
                        artifact_id = stem.removesuffix(".err")
                    else:
                        kind = "unknown"
                        artifact_id = stem
                    entries.append(
                        LogFileEntry(
                            qualified_id=f"(orphan) {artifact_id}",
                            kind=kind,
                            path=str(log_file),
                            size_bytes=log_file.stat().st_size,
                        )
                    )

    return logs_dir, entries


@instrument_action("list_logs")
def list_logs(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    job_filter: str | None = None,
    state_root: Path | None = None,
) -> LogsListResult:
    """List wrapper log files for one project."""
    MetricsService().increment("logs.list.calls")
    validation = validate_project(project_path, schedule_name=schedule_name)
    if not validation.valid or validation.normalized_manifest is None:
        return LogsListResult(valid=False, validation=validation, error="project validation failed")

    project_id = validation.normalized_manifest.project_id
    logs_dir, entries = _collect_log_files(validation, state_root=state_root, job_filter=job_filter)

    LOGGER.info(
        "logs_listed",
        project_id=project_id,
        file_count=len(entries),
        total_bytes=sum(e.size_bytes for e in entries),
    )
    return LogsListResult(
        valid=True,
        project_id=project_id,
        logs_dir=logs_dir,
        files=tuple(entries),
        validation=validation,
    )


@instrument_action("clear_logs")
def clear_logs(
    project_path: str | Path | None = None,
    *,
    schedule_name: str | None = None,
    job_filter: str | None = None,
    state_root: Path | None = None,
    dry_run: bool = True,
) -> LogsClearResult:
    """Clear (truncate) wrapper log files for one project."""
    metrics = MetricsService()
    metrics.increment("logs.clear.calls")
    validation = validate_project(project_path, schedule_name=schedule_name)
    if not validation.valid or validation.normalized_manifest is None:
        return LogsClearResult(valid=False, validation=validation, error="project validation failed")

    project_id = validation.normalized_manifest.project_id
    _, entries = _collect_log_files(validation, state_root=state_root, job_filter=job_filter)

    cleared = 0
    if not dry_run:
        for entry in entries:
            path = Path(entry.path)
            if path.exists() and entry.size_bytes > 0:
                path.write_text("", encoding="utf-8")
                cleared += 1
                LOGGER.info("log_cleared", path=entry.path, previous_bytes=entry.size_bytes)
        metrics.increment("logs.cleared", cleared)

    LOGGER.info(
        "logs_clear_completed",
        project_id=project_id,
        dry_run=dry_run,
        file_count=len(entries),
        cleared=cleared,
    )
    return LogsClearResult(
        valid=True,
        project_id=project_id,
        dry_run=dry_run,
        files=tuple(entries),
        cleared=cleared,
        validation=validation,
    )

"""Installed local wrapper-log provider with strict owned-path containment."""

from __future__ import annotations

from pathlib import Path

from xcron.contracts import (
    InvocationContext,
    LogFileEntry,
    LogPort,
    LogsClearResult,
    LogsListResult,
    LogsRequest,
    ProjectRequest,
    ScheduleControlPort,
    WorkspacePort,
)
from xcron.kernel import (
    Capability,
    CapabilityDescriptor,
    CapabilityProvides,
    CapabilityRegistration,
    CapabilityRequirement,
)


class LocalLogProvider:
    """Read and truncate logs that are provably within xcron-owned paths."""

    def __init__(self, workspace: WorkspacePort, scheduler: ScheduleControlPort) -> None:
        self._workspace = workspace
        self._scheduler = scheduler

    def list(self, request: LogsRequest, context: InvocationContext) -> LogsListResult:
        validation = self._scheduler.validate(
            ProjectRequest(schedule_name=request.schedule_name),
            context,
        )
        if not validation.valid or validation.normalized_manifest is None:
            return LogsListResult(valid=False, validation=validation, error="project validation failed")
        logs_dir, entries = self._collect(validation, request, context)
        return LogsListResult(
            valid=True,
            project_id=validation.normalized_manifest.project_id,
            logs_dir=str(logs_dir) if logs_dir is not None else None,
            files=tuple(entries),
            validation=validation,
        )

    def clear(self, request: LogsRequest, context: InvocationContext) -> LogsClearResult:
        listed = self.list(request, context)
        if not listed.valid:
            return LogsClearResult(valid=False, validation=listed.validation, error=listed.error)
        cleared = 0
        logs_dir = Path(listed.logs_dir) if listed.logs_dir is not None else None
        if not request.dry_run and logs_dir is not None:
            for entry in listed.files:
                path = Path(entry.path)
                if entry.size_bytes > 0 and _is_owned_log(path, logs_dir):
                    path.write_text("", encoding="utf-8")
                    cleared += 1
        return LogsClearResult(
            valid=True,
            project_id=listed.project_id,
            dry_run=request.dry_run,
            files=listed.files,
            cleared=cleared,
            validation=listed.validation,
        )

    def _collect(self, validation, request: LogsRequest, context: InvocationContext) -> tuple[Path | None, list[LogFileEntry]]:
        manifest = validation.normalized_manifest
        assert manifest is not None
        entries: list[LogFileEntry] = []
        logs_dir: Path | None = None
        state_root = context.settings.state_root or context.options.state_root
        for job in manifest.jobs:
            if request.job_filter and job.job_id != request.job_filter and job.qualified_id != request.job_filter:
                continue
            paths = self._workspace.runtime_paths(job, state_root=state_root)
            logs_dir = paths.logs_dir
            for kind, path in (
                ("stdout", paths.stdout_log_path),
                ("stderr", paths.stderr_log_path),
                ("events", paths.event_log_path),
            ):
                if _is_owned_log(path, paths.logs_dir):
                    entries.append(
                        LogFileEntry(job.qualified_id, kind, str(path), path.stat().st_size)
                    )
        if logs_dir is not None and not request.job_filter and logs_dir.is_dir():
            known_paths = {entry.path for entry in entries}
            for path in sorted((*logs_dir.glob("*.log"), *logs_dir.glob("*.jsonl"))):
                if str(path) in known_paths or not _is_owned_log(path, logs_dir):
                    continue
                entries.append(
                    LogFileEntry(
                        qualified_id=f"(orphan) {_artifact_id(path)}",
                        kind=_kind(path),
                        path=str(path),
                        size_bytes=path.stat().st_size,
                    )
                )
        return logs_dir, entries


def _is_owned_log(path: Path, logs_dir: Path) -> bool:
    """Reject missing, non-file, and symlinked paths escaping the owned root."""
    try:
        return path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(logs_dir.resolve())
    except OSError:
        return False


def _kind(path: Path) -> str:
    if path.name.endswith(".out.log"):
        return "stdout"
    if path.name.endswith(".err.log"):
        return "stderr"
    if path.name.endswith(".events.jsonl"):
        return "events"
    return "unknown"


def _artifact_id(path: Path) -> str:
    for suffix in (".out.log", ".err.log", ".events.jsonl"):
        if path.name.endswith(suffix):
            return path.name.removesuffix(suffix)
    return path.stem


DESCRIPTOR = CapabilityDescriptor(
    capability="logs",
    implementation="local",
    version="0.1.2",
    kernel_api=">=1,<2",
    requires=(CapabilityRequirement("workspace"), CapabilityRequirement("scheduler")),
    provides=CapabilityProvides(ports=("logs",), cli_paths=("logs",)),
)


def _build(host) -> CapabilityRegistration:
    return CapabilityRegistration(
        ports={
            "logs": LocalLogProvider(
                host.require("workspace", WorkspacePort),
                host.require("scheduler", ScheduleControlPort),
            )
        },
        cli_paths={"logs": None},
    )


CAPABILITY = Capability(DESCRIPTOR, _build)

assert isinstance(LocalLogProvider.__new__(LocalLogProvider), LogPort)

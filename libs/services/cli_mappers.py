"""Mapping helpers from action results to typed CLI response envelopes."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

from libs.services.axi_presenter import collapse_home_path, truncate_text
from libs.services.cli_contracts import CommandContract
from libs.services.cli_responses import (
    ErrorDetail,
    ErrorResponse,
    HomeJobsSummary,
    HomeResponse,
    InspectResponse,
    JobListRow,
    JobsListResponse,
    JobsShowResponse,
    MutationResponse,
    PlanChangeRow,
    PlanResponse,
    StatusResponse,
    StatusRow,
    SummaryRow,
    ValidationSummaryResponse,
)


def map_error_response(
    message: str,
    *,
    code: str = "runtime_error",
    details: Sequence[dict[str, str]] = (),
    help_items: Sequence[str] = (),
) -> ErrorResponse:
    return ErrorResponse(
        kind="error",
        code=code,
        message=message,
        details=tuple(ErrorDetail(**item) for item in details),
        help=tuple(help_items),
    )


def map_home_response(
    result: Any,
    *,
    executable: str,
    contract: CommandContract,
    include_plan_changes: bool,
) -> HomeResponse:
    counts = Counter(change.kind.value for change in result.changes)
    return HomeResponse(
        bin=collapse_home_path(executable),
        description="Manage project-local schedules against native OS schedulers",
        project=result.validation.project_root,
        schedule=Path(result.validation.manifest_path).stem if result.validation.manifest_path else None,
        backend=result.backend,
        manifest=result.validation.manifest_path,
        jobs=HomeJobsSummary(total=len(result.validation.normalized_manifest.jobs)),
        plan_summary=tuple(SummaryRow(kind=kind, count=count) for kind, count in sorted(counts.items())),
        plan_changes=tuple(
            PlanChangeRow(kind=change.kind.value, id=change.qualified_id, reason=change.reason)
            for change in result.changes
        )
        if include_plan_changes
        else tuple(),
        help=tuple(contract.default_hints),
    )


def map_validation_response(result: Any) -> ValidationSummaryResponse:
    return ValidationSummaryResponse(
        project=result.project_root,
        manifest=result.manifest_path,
        valid=True,
        jobs=len(result.normalized_manifest.jobs),
        manifest_hash=result.hashes.manifest_hash,
        errors=len(result.errors),
        warnings=len(result.warnings),
        warning_messages=tuple(f"{message.path}: {message.message}" for message in result.warnings),
    )


def map_plan_response(result: Any, *, contract: CommandContract) -> PlanResponse:
    return PlanResponse(
        backend=result.backend,
        state=result.state_path,
        count=f"{len(result.changes)} of {len(result.changes)}",
        changes=tuple(
            PlanChangeRow(kind=change.kind.value, id=change.qualified_id, reason=change.reason)
            for change in result.changes
        ),
        help=tuple(contract.default_hints),
    )


def map_apply_response(result: Any, *, contract: CommandContract) -> MutationResponse:
    non_noop_changes = [change for change in result.plan_result.changes if change.kind.value != "noop"]
    return MutationResponse(
        kind=contract.name,
        target=result.plan_result.validation.normalized_manifest.project_id,
        outcome="noop" if not non_noop_changes else "applied",
        backend=result.backend,
        count=len(non_noop_changes),
        manifest=result.plan_result.validation.manifest_path,
        help=tuple(contract.default_hints),
    )


def map_status_response(result: Any, *, contract: CommandContract) -> StatusResponse:
    return StatusResponse(
        backend=result.backend,
        count=f"{len(result.statuses)} of {len(result.statuses)}",
        statuses=tuple(
            StatusRow(kind=entry.kind.value, id=entry.qualified_id, reason=entry.reason)
            for entry in result.statuses
        ),
        help=tuple(contract.default_hints),
    )


def map_inspect_response(
    result: Any,
    *,
    contract: CommandContract,
    job_id: str,
    full: bool,
) -> InspectResponse:
    return InspectResponse(
        backend=result.backend,
        job=result.desired_job.qualified_id if result.desired_job is not None else job_id,
        status=result.status_entry.kind.value if result.status_entry is not None else "unknown",
        desired={field.name: field.value for field in result.desired_fields},
        deployed={field.name: field.value for field in result.deployed_fields},
        snippets={
            snippet.name: (
                snippet.content
                if full
                else truncate_text(
                    snippet.content,
                    limit=contract.truncation_limit or 1000,
                    full_hint=f"Run `xcron inspect {job_id} --full` to see complete content",
                )
            )
            for snippet in result.snippets
        },
        help=tuple(contract.default_hints),
    )


def map_jobs_list_response(result: Any, *, contract: CommandContract) -> JobsListResponse:
    return JobsListResponse(
        manifest=result.manifest_path,
        count=f"{len(result.jobs)} of {len(result.jobs)}",
        jobs=tuple(
            JobListRow(
                job_id=job.job_id,
                enabled=job.enabled,
                schedule=f"{job.schedule.kind.value}={job.schedule.value}",
                command=job.execution.command,
            )
            for job in result.jobs
        ),
        help=tuple(contract.default_hints),
    )


def map_jobs_show_response(result: Any, *, contract: CommandContract) -> JobsShowResponse:
    return JobsShowResponse(
        manifest=result.manifest_path,
        job=result.job.qualified_id,
        enabled=result.job.enabled,
        schedule=f"{result.job.schedule.kind.value}={result.job.schedule.value}",
        command=result.job.execution.command,
        working_dir=result.job.execution.working_dir,
        shell=result.job.execution.shell,
        overlap=result.job.execution.overlap.value,
        description=result.job.description,
        env=tuple(f"{key}={value}" for key, value in result.job.execution.env),
        help=tuple(contract.default_hints),
    )


def map_jobs_mutation_response(
    result: Any,
    *,
    contract: CommandContract,
    changed_outcome: str,
) -> MutationResponse:
    target = None
    if getattr(result, "job", None) is not None:
        target = result.job.qualified_id
    elif getattr(result, "removed_job_identifier", None) is not None:
        target = result.removed_job_identifier

    return MutationResponse(
        kind=contract.name,
        target=target,
        outcome=changed_outcome if getattr(result, "changed", True) else "noop",
        manifest=result.manifest_path,
        help=tuple(contract.default_hints),
    )


def map_prune_response(result: Any, *, contract: CommandContract) -> MutationResponse:
    return MutationResponse(
        kind=contract.name,
        target=result.project_id,
        outcome="noop" if not result.removed else "pruned",
        backend=result.backend,
        count=len(result.removed),
        help=tuple(contract.default_hints),
    )


__all__ = [
    "map_apply_response",
    "map_error_response",
    "map_home_response",
    "map_inspect_response",
    "map_jobs_list_response",
    "map_jobs_mutation_response",
    "map_jobs_show_response",
    "map_plan_response",
    "map_prune_response",
    "map_status_response",
    "map_validation_response",
]

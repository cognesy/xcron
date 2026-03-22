"""Backend-neutral planning and diffing models for xcron."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from libs.domain.models import NormalizedJob, NormalizedManifest


class PlanChangeKind(str, Enum):
    """Kinds of plan changes supported by xcron v1."""

    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"
    ENABLE = "enable"
    DISABLE = "disable"
    NOOP = "noop"
    DRIFT = "drift"
    ERROR = "error"


class StatusKind(str, Enum):
    """Operator-facing status kinds for one managed job or extra artifact."""

    OK = "ok"
    MISSING = "missing"
    DRIFT = "drift"
    DISABLED = "disabled"
    EXTRA = "extra"
    ERROR = "error"


@dataclass(frozen=True)
class DeployedJobState:
    """Derived local record for one managed deployed job."""

    qualified_id: str
    job_id: str
    artifact_id: str
    backend: str
    enabled: bool
    desired_hash: str
    definition_hash: str | None = None
    observed_hash: str | None = None
    label: str | None = None
    artifact_path: str | None = None
    wrapper_path: str | None = None
    stdout_log_path: str | None = None
    stderr_log_path: str | None = None
    last_applied_at: str | None = None


@dataclass(frozen=True)
class ProjectState:
    """Per-project derived state stored locally on one machine."""

    project_id: str
    backend: str
    manifest_hash: str | None
    jobs: tuple[DeployedJobState, ...] = field(default_factory=tuple)
    updated_at: str | None = None


@dataclass(frozen=True)
class PlanChange:
    """One desired-vs-actual reconciliation change."""

    kind: PlanChangeKind
    qualified_id: str
    reason: str
    desired_job: NormalizedJob | None = None
    deployed_job: DeployedJobState | None = None
    desired_hash: str | None = None
    deployed_hash: str | None = None


@dataclass(frozen=True)
class StatusEntry:
    """Operator-facing status entry derived from one plan change."""

    kind: StatusKind
    qualified_id: str
    reason: str
    desired_job: NormalizedJob | None = None
    deployed_job: DeployedJobState | None = None


@dataclass(frozen=True)
class ProjectPlan:
    """Structured plan result for one project."""

    backend: str
    manifest: NormalizedManifest
    changes: tuple[PlanChange, ...]
    state: ProjectState


def build_project_plan(
    manifest: NormalizedManifest,
    backend: str,
    desired_manifest_hash: str,
    desired_job_hashes: dict[str, str],
    desired_definition_hashes: dict[str, str],
    state: ProjectState,
) -> ProjectPlan:
    """Compute the desired-vs-deployed diff for one project."""
    deployed_by_id = {job.qualified_id: job for job in state.jobs}
    desired_by_id = {job.qualified_id: job for job in manifest.jobs}
    changes: list[PlanChange] = []

    for desired_job in manifest.jobs:
        desired_hash = desired_job_hashes[desired_job.qualified_id]
        desired_definition_hash = desired_definition_hashes[desired_job.qualified_id]
        deployed_job = deployed_by_id.get(desired_job.qualified_id)
        if deployed_job is None:
            changes.append(
                PlanChange(
                    kind=PlanChangeKind.CREATE,
                    qualified_id=desired_job.qualified_id,
                    reason="job not present in derived local state",
                    desired_job=desired_job,
                    desired_hash=desired_hash,
                )
            )
            continue

        if deployed_job.observed_hash is not None and deployed_job.observed_hash != deployed_job.desired_hash:
            changes.append(
                PlanChange(
                    kind=PlanChangeKind.DRIFT,
                    qualified_id=desired_job.qualified_id,
                    reason="observed managed artifact hash differs from last applied hash",
                    desired_job=desired_job,
                    deployed_job=deployed_job,
                    desired_hash=desired_hash,
                    deployed_hash=deployed_job.desired_hash,
                )
            )
            continue

        if deployed_job.backend != backend:
            changes.append(
                PlanChange(
                    kind=PlanChangeKind.UPDATE,
                    qualified_id=desired_job.qualified_id,
                    reason=f"backend changed from {deployed_job.backend} to {backend}",
                    desired_job=desired_job,
                    deployed_job=deployed_job,
                    desired_hash=desired_hash,
                    deployed_hash=deployed_job.desired_hash,
                )
            )
            continue

        deployed_definition_hash = deployed_job.definition_hash or deployed_job.desired_hash
        if deployed_definition_hash != desired_definition_hash:
            changes.append(
                PlanChange(
                    kind=PlanChangeKind.UPDATE,
                    qualified_id=desired_job.qualified_id,
                    reason="normalized job definition hash changed",
                    desired_job=desired_job,
                    deployed_job=deployed_job,
                    desired_hash=desired_hash,
                    deployed_hash=deployed_job.desired_hash,
                )
            )
            continue

        if desired_job.enabled and not deployed_job.enabled:
            changes.append(
                PlanChange(
                    kind=PlanChangeKind.ENABLE,
                    qualified_id=desired_job.qualified_id,
                    reason="job is disabled in deployed state but enabled in desired state",
                    desired_job=desired_job,
                    deployed_job=deployed_job,
                    desired_hash=desired_hash,
                    deployed_hash=deployed_job.desired_hash,
                )
            )
            continue

        if not desired_job.enabled and deployed_job.enabled:
            changes.append(
                PlanChange(
                    kind=PlanChangeKind.DISABLE,
                    qualified_id=desired_job.qualified_id,
                    reason="job is enabled in deployed state but disabled in desired state",
                    desired_job=desired_job,
                    deployed_job=deployed_job,
                    desired_hash=desired_hash,
                    deployed_hash=deployed_job.desired_hash,
                )
            )
            continue

        changes.append(
            PlanChange(
                kind=PlanChangeKind.NOOP,
                qualified_id=desired_job.qualified_id,
                reason="desired definition and enabled state match deployed state",
                desired_job=desired_job,
                deployed_job=deployed_job,
                desired_hash=desired_hash,
                deployed_hash=deployed_job.desired_hash,
            )
        )

    for deployed_job in sorted(state.jobs, key=lambda item: item.qualified_id):
        if deployed_job.qualified_id in desired_by_id:
            continue
        changes.append(
            PlanChange(
                kind=PlanChangeKind.REMOVE,
                qualified_id=deployed_job.qualified_id,
                reason="job exists in derived local state but not in desired manifest",
                deployed_job=deployed_job,
                deployed_hash=deployed_job.desired_hash,
            )
        )

    ordered_changes = tuple(sorted(changes, key=lambda item: (item.qualified_id, item.kind.value)))
    manifest_state = ProjectState(
        project_id=state.project_id or manifest.project_id,
        backend=backend,
        manifest_hash=desired_manifest_hash,
        jobs=state.jobs,
        updated_at=state.updated_at,
    )
    return ProjectPlan(
        backend=backend,
        manifest=manifest,
        changes=ordered_changes,
        state=manifest_state,
    )


def build_status_entries(plan: ProjectPlan) -> tuple[StatusEntry, ...]:
    """Project operator-facing status entries from one reconciliation plan."""
    entries: list[StatusEntry] = []
    for change in plan.changes:
        entries.append(
            StatusEntry(
                kind=status_kind_for_change(change),
                qualified_id=change.qualified_id,
                reason=status_reason_for_change(change),
                desired_job=change.desired_job,
                deployed_job=change.deployed_job,
            )
        )
    return tuple(entries)


def status_kind_for_change(change: PlanChange) -> StatusKind:
    """Map one plan change to an operator-facing status kind."""
    if change.kind is PlanChangeKind.REMOVE:
        return StatusKind.EXTRA
    if change.kind is PlanChangeKind.ERROR:
        return StatusKind.ERROR
    if change.kind in (PlanChangeKind.DRIFT, PlanChangeKind.UPDATE, PlanChangeKind.ENABLE, PlanChangeKind.DISABLE):
        return StatusKind.DRIFT
    if change.kind is PlanChangeKind.CREATE:
        return StatusKind.DISABLED if change.desired_job is not None and not change.desired_job.enabled else StatusKind.MISSING
    if change.kind is PlanChangeKind.NOOP:
        return StatusKind.DISABLED if change.desired_job is not None and not change.desired_job.enabled else StatusKind.OK
    raise ValueError(f"unsupported plan change kind for status projection: {change.kind}")


def status_reason_for_change(change: PlanChange) -> str:
    """Return the operator-facing reason for one projected status entry."""
    kind = status_kind_for_change(change)
    if kind is StatusKind.DISABLED and change.desired_job is not None and not change.desired_job.enabled:
        return "job is disabled in desired state"
    if kind is StatusKind.MISSING:
        return "job is not installed in actual backend state"
    if kind is StatusKind.OK:
        return "desired definition and actual backend state are aligned"
    if kind is StatusKind.EXTRA:
        return "managed backend artifact exists but no desired job matches it"
    if kind is StatusKind.DRIFT:
        return change.reason
    if kind is StatusKind.ERROR:
        return change.reason
    return change.reason

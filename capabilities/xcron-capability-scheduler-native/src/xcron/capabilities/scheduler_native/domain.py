"""Pure native-scheduler planning projections over public contract values."""

from __future__ import annotations

from xcron.contracts import (
    DeployedJobState,
    NormalizedManifest,
    PlanChange,
    PlanChangeKind,
    ProjectPlan,
    ProjectState,
    StatusEntry,
    StatusKind,
)

__all__ = [
    "DeployedJobState",
    "PlanChange",
    "PlanChangeKind",
    "ProjectPlan",
    "ProjectState",
    "StatusEntry",
    "StatusKind",
    "build_project_plan",
    "build_status_entries",
    "status_kind_for_change",
    "status_reason_for_change",
]


def build_project_plan(
    manifest: NormalizedManifest,
    backend: str,
    desired_manifest_hash: str,
    desired_job_hashes: dict[str, str],
    desired_definition_hashes: dict[str, str],
    state: ProjectState,
) -> ProjectPlan:
    """Compute the desired-versus-deployed diff for one project."""
    deployed_by_id = {job.qualified_id: job for job in state.jobs}
    desired_by_id = {job.qualified_id: job for job in manifest.jobs}
    changes: list[PlanChange] = []

    for desired_job in manifest.jobs:
        desired_hash = desired_job_hashes[desired_job.qualified_id]
        desired_definition_hash = desired_definition_hashes[desired_job.qualified_id]
        deployed_job = deployed_by_id.get(desired_job.qualified_id)
        if deployed_job is None:
            changes.append(PlanChange(PlanChangeKind.CREATE, desired_job.qualified_id, "job not present in derived local state", desired_job=desired_job, desired_hash=desired_hash))
            continue
        if deployed_job.observed_hash is not None and deployed_job.observed_hash != deployed_job.desired_hash:
            changes.append(PlanChange(PlanChangeKind.DRIFT, desired_job.qualified_id, "observed managed artifact hash differs from last applied hash", desired_job=desired_job, deployed_job=deployed_job, desired_hash=desired_hash, deployed_hash=deployed_job.desired_hash))
            continue
        if deployed_job.backend != backend:
            changes.append(PlanChange(PlanChangeKind.UPDATE, desired_job.qualified_id, f"backend changed from {deployed_job.backend} to {backend}", desired_job=desired_job, deployed_job=deployed_job, desired_hash=desired_hash, deployed_hash=deployed_job.desired_hash))
            continue
        deployed_definition_hash = deployed_job.definition_hash or deployed_job.desired_hash
        if deployed_definition_hash != desired_definition_hash:
            changes.append(PlanChange(PlanChangeKind.UPDATE, desired_job.qualified_id, "normalized job definition hash changed", desired_job=desired_job, deployed_job=deployed_job, desired_hash=desired_hash, deployed_hash=deployed_job.desired_hash))
            continue
        if desired_job.enabled and not deployed_job.enabled:
            changes.append(PlanChange(PlanChangeKind.ENABLE, desired_job.qualified_id, "job is disabled in deployed state but enabled in desired state", desired_job=desired_job, deployed_job=deployed_job, desired_hash=desired_hash, deployed_hash=deployed_job.desired_hash))
            continue
        if not desired_job.enabled and deployed_job.enabled:
            changes.append(PlanChange(PlanChangeKind.DISABLE, desired_job.qualified_id, "job is enabled in deployed state but disabled in desired state", desired_job=desired_job, deployed_job=deployed_job, desired_hash=desired_hash, deployed_hash=deployed_job.desired_hash))
            continue
        changes.append(PlanChange(PlanChangeKind.NOOP, desired_job.qualified_id, "desired definition and enabled state match deployed state", desired_job=desired_job, deployed_job=deployed_job, desired_hash=desired_hash, deployed_hash=deployed_job.desired_hash))

    for deployed_job in sorted(state.jobs, key=lambda item: item.qualified_id):
        if deployed_job.qualified_id not in desired_by_id:
            changes.append(PlanChange(PlanChangeKind.REMOVE, deployed_job.qualified_id, "job exists in derived local state but not in desired manifest", deployed_job=deployed_job, deployed_hash=deployed_job.desired_hash))

    ordered_changes = tuple(sorted(changes, key=lambda item: (item.qualified_id, item.kind.value)))
    manifest_state = ProjectState(state.project_id or manifest.project_id, backend, desired_manifest_hash, state.jobs, state.updated_at)
    return ProjectPlan(backend, manifest, ordered_changes, manifest_state)


def build_status_entries(plan: ProjectPlan) -> tuple[StatusEntry, ...]:
    return tuple(StatusEntry(status_kind_for_change(change), change.qualified_id, status_reason_for_change(change), change.desired_job, change.deployed_job) for change in plan.changes)


def status_kind_for_change(change: PlanChange) -> StatusKind:
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
    kind = status_kind_for_change(change)
    if kind is StatusKind.DISABLED and change.desired_job is not None and not change.desired_job.enabled:
        return "job is disabled in desired state"
    if kind is StatusKind.MISSING:
        return "job is not installed in actual backend state"
    if kind is StatusKind.OK:
        return "desired definition and actual backend state are aligned"
    if kind is StatusKind.EXTRA:
        return "managed backend artifact exists but no desired job matches it"
    return change.reason

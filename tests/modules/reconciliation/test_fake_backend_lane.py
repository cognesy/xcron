"""Reconciliation driven entirely through its own port, with no real adapter.

This lane exists to prove the module is testable without launchd, cron, or any
sibling implementation. It imports `api`, `contracts`, and `ports` only — the
same surface a third-party scheduler would build against. If reconciliation ever
grows a hidden dependency on a concrete adapter, these tests fail.
"""

from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from xcron.capabilities.reconciliation.api import (
    SchedulerRegistry,
    apply_project,
    plan_project,
    prune_project,
    status_project,
)
from xcron.capabilities.reconciliation.contracts import (
    PlanChange,
    PlanChangeKind,
    ProjectState,
    StatusKind,
    UnknownSchedulerBackendError,
)
from xcron.capabilities.reconciliation.ports import (
    DeploymentPlan,
    SchedulerInspection,
    SchedulerRuntimeOptions,
)

MANIFEST = """\
version: 1
project:
  id: fake-lane
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: alpha
    schedule:
      cron: "0 * * * *"
    command: echo alpha
  - id: beta
    schedule:
      cron: "30 * * * *"
    command: echo beta
"""


class FakeScheduler:
    """An in-memory scheduler that records what reconciliation asked it to do."""

    name = "fake"

    def __init__(self, *, deployed: ProjectState | None = None) -> None:
        self._deployed = deployed
        self.applied: list[DeploymentPlan] = []
        self.pruned: list[str] = []

    def collect_project_state(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> ProjectState:
        if self._deployed is not None:
            return self._deployed
        return ProjectState(project_id=project_id, backend=self.name, manifest_hash=None)

    def inspect_project(
        self,
        project_id: str,
        *,
        options: SchedulerRuntimeOptions,
        include_native_detail: bool = False,
    ) -> tuple[SchedulerInspection, ...]:
        return tuple()

    def apply(
        self, deployment: DeploymentPlan, *, options: SchedulerRuntimeOptions
    ) -> ProjectState:
        self.applied.append(deployment)
        return ProjectState(
            project_id=deployment.plan.manifest.project_id,
            backend=self.name,
            manifest_hash=deployment.manifest_hash,
        )

    def prune_project(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> tuple[SchedulerInspection, ...]:
        self.pruned.append(project_id)
        return tuple()

    def schedule_errors(self, jobs) -> tuple[PlanChange, ...]:
        return tuple()


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    schedules = root / "resources" / "schedules"
    schedules.mkdir(parents=True)
    (schedules / "default.yaml").write_text(textwrap.dedent(MANIFEST), encoding="utf-8")
    return root


def _registry(backend: FakeScheduler) -> SchedulerRegistry:
    return SchedulerRegistry((backend,))


def test_plan_reports_every_desired_job_as_a_create_against_empty_state(project: Path) -> None:
    result = plan_project(project, backend="fake", scheduler_registry=_registry(FakeScheduler()))

    assert result.valid is True
    assert result.backend == "fake"
    assert {change.kind for change in result.changes} == {PlanChangeKind.CREATE}
    assert sorted(change.qualified_id for change in result.changes) == [
        "fake-lane.alpha",
        "fake-lane.beta",
    ]


def test_status_marks_undeployed_jobs_missing(project: Path) -> None:
    result = status_project(project, backend="fake", scheduler_registry=_registry(FakeScheduler()))

    assert result.valid is True
    assert {entry.kind for entry in result.statuses} == {StatusKind.MISSING}


def test_apply_hands_the_backend_a_deployment_plan_and_returns_its_state(
    project: Path, tmp_path: Path
) -> None:
    backend = FakeScheduler()
    result = apply_project(
        project,
        backend="fake",
        scheduler_registry=_registry(backend),
        state_root=tmp_path / "state",
    )

    assert result.valid is True
    assert len(backend.applied) == 1

    deployment = backend.applied[0]
    assert deployment.backend == "fake"
    assert deployment.plan.manifest.project_id == "fake-lane"
    assert set(deployment.job_hashes) == {"fake-lane.alpha", "fake-lane.beta"}
    assert result.applied_state is not None
    assert result.applied_state.manifest_hash == deployment.manifest_hash


def test_prune_asks_the_backend_to_remove_only_this_project(project: Path, tmp_path: Path) -> None:
    backend = FakeScheduler()
    result = prune_project(
        project,
        backend="fake",
        scheduler_registry=_registry(backend),
        state_root=tmp_path / "state",
    )

    assert result.valid is True
    assert backend.pruned == ["fake-lane"]


def test_a_backend_reporting_a_schedule_error_blocks_apply(project: Path, tmp_path: Path) -> None:
    class RejectingScheduler(FakeScheduler):
        name = "rejecting"

        def schedule_errors(self, jobs) -> tuple[PlanChange, ...]:
            job = jobs[0]
            return (
                PlanChange(
                    kind=PlanChangeKind.ERROR,
                    qualified_id=job.qualified_id,
                    reason="unsupported by this backend",
                    desired_job=job,
                ),
            )

        def apply(self, deployment, *, options):
            raise AssertionError("apply must not run when schedule validation fails")

    backend = RejectingScheduler()
    result = apply_project(
        project,
        backend="rejecting",
        scheduler_registry=_registry(backend),
        state_root=tmp_path / "state",
    )

    assert result.valid is False
    assert result.backend == "rejecting"
    assert backend.applied == []


def test_an_unregistered_backend_raises_the_modules_typed_error(project: Path) -> None:
    registry = _registry(FakeScheduler())

    with pytest.raises(UnknownSchedulerBackendError) as excinfo:
        status_project(project, backend="absent", scheduler_registry=registry)

    assert excinfo.value.backend_name == "absent"
    assert excinfo.value.available == ("fake",)

from __future__ import annotations

import textwrap

import pytest

from libs.actions.apply_project import apply_project
from libs.actions.plan_project import plan_project
from libs.actions.validate_project import validate_project
from libs.domain import DeployedJobState, ProjectState
from libs.domain.diffing import PlanChangeKind
from libs.services.state_store import save_project_state


def _make_every_project(tmp_path, every_value: str):
    """Return a project path containing one job with the given every schedule."""
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(f"""\
            version: 1
            project:
              id: compat-test
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: job
                schedule:
                  every: "{every_value}"
                command: echo test
            """),
        encoding="utf-8",
    )
    return project


@pytest.mark.parametrize("every_value", ["30s", "1s", "59s"])
def test_plan_cron_rejects_sub_minute_every(tmp_path, every_value) -> None:
    project = _make_every_project(tmp_path, every_value)
    result = plan_project(project, backend="cron", platform="linux")
    error_changes = [c for c in result.changes if c.kind is PlanChangeKind.ERROR]
    assert error_changes, f"expected an ERROR change for every={every_value!r} with cron backend"
    assert "sub-minute" in error_changes[0].reason


@pytest.mark.parametrize("every_value", ["2w", "3w", "52w"])
def test_plan_cron_rejects_multi_week_every(tmp_path, every_value) -> None:
    project = _make_every_project(tmp_path, every_value)
    result = plan_project(project, backend="cron", platform="linux")
    error_changes = [c for c in result.changes if c.kind is PlanChangeKind.ERROR]
    assert error_changes, f"expected an ERROR change for every={every_value!r} with cron backend"
    assert "multi-week" in error_changes[0].reason


@pytest.mark.parametrize("every_value", ["1m", "15m", "1h", "4h", "1d", "1w"])
def test_plan_cron_accepts_valid_every(tmp_path, every_value) -> None:
    project = _make_every_project(tmp_path, every_value)
    result = plan_project(project, backend="cron", platform="linux")
    error_changes = [c for c in result.changes if c.kind is PlanChangeKind.ERROR]
    assert not error_changes, f"unexpected ERROR for every={every_value!r} with cron backend: {error_changes}"


@pytest.mark.parametrize("every_value", ["30s", "2w"])
def test_plan_launchd_accepts_any_every(tmp_path, every_value) -> None:
    project = _make_every_project(tmp_path, every_value)
    result = plan_project(project, backend="launchd", state_root=tmp_path / "state", platform="darwin")
    error_changes = [c for c in result.changes if c.kind is PlanChangeKind.ERROR]
    assert not error_changes, f"unexpected ERROR for every={every_value!r} with launchd backend"


def test_plan_project_reports_full_change_set(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: demo-app
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: alpha
                schedule:
                  cron: "0 * * * *"
                command: echo alpha
              - id: beta
                enabled: false
                schedule:
                  cron: "15 * * * *"
                command: echo beta
              - id: gamma
                schedule:
                  cron: "30 * * * *"
                command: echo gamma-v2
              - id: delta
                schedule:
                  cron: "45 * * * *"
                command: echo delta
              - id: epsilon
                schedule:
                  cron: "*/5 * * * *"
                command: echo epsilon
            """
        ),
        encoding="utf-8",
    )

    state_root = tmp_path / "state-root"
    empty_plan = plan_project(project, backend="launchd", state_root=state_root, platform="darwin")
    assert [change.kind.value for change in empty_plan.changes] == ["create"] * 5

    validation = validate_project(project)
    assert validation.hashes is not None
    assert validation.normalized_manifest is not None
    jobs = {job.qualified_id: job for job in validation.normalized_manifest.jobs}

    save_project_state(
        ProjectState(
            project_id="demo-app",
            backend="launchd",
            manifest_hash="old-manifest",
            jobs=(
                DeployedJobState(
                    qualified_id="demo-app.alpha",
                    job_id="alpha",
                    artifact_id=jobs["demo-app.alpha"].artifact_id,
                    backend="launchd",
                    enabled=True,
                    desired_hash=validation.hashes.job_hashes["demo-app.alpha"],
                    definition_hash=validation.hashes.job_definition_hashes["demo-app.alpha"],
                ),
                DeployedJobState(
                    qualified_id="demo-app.beta",
                    job_id="beta",
                    artifact_id=jobs["demo-app.beta"].artifact_id,
                    backend="launchd",
                    enabled=True,
                    desired_hash="old-beta-hash",
                    definition_hash=validation.hashes.job_definition_hashes["demo-app.beta"],
                ),
                DeployedJobState(
                    qualified_id="demo-app.gamma",
                    job_id="gamma",
                    artifact_id=jobs["demo-app.gamma"].artifact_id,
                    backend="launchd",
                    enabled=True,
                    desired_hash="old-gamma-hash",
                    definition_hash="old-gamma-definition",
                ),
                DeployedJobState(
                    qualified_id="demo-app.delta",
                    job_id="delta",
                    artifact_id=jobs["demo-app.delta"].artifact_id,
                    backend="launchd",
                    enabled=True,
                    desired_hash=validation.hashes.job_hashes["demo-app.delta"],
                    definition_hash=validation.hashes.job_definition_hashes["demo-app.delta"],
                    observed_hash="manually-edited",
                ),
                DeployedJobState(
                    qualified_id="demo-app.legacy",
                    job_id="legacy",
                    artifact_id="demo-app.legacy",
                    backend="launchd",
                    enabled=True,
                    desired_hash="legacy-hash",
                    definition_hash="legacy-definition",
                ),
            ),
        ),
        state_root=state_root,
    )

    mixed_plan = plan_project(project, backend="launchd", state_root=state_root, platform="darwin")
    assert [(change.qualified_id, change.kind.value) for change in mixed_plan.changes] == [
        ("demo-app.alpha", "noop"),
        ("demo-app.beta", "disable"),
        ("demo-app.delta", "drift"),
        ("demo-app.epsilon", "create"),
        ("demo-app.gamma", "update"),
        ("demo-app.legacy", "remove"),
    ]


@pytest.mark.parametrize("every_value,expected_fragment", [
    ("30s", "sub-minute"),
    ("2w",  "multi-week"),
])
def test_apply_cron_rejects_inexpressible_every_without_crash(tmp_path, every_value, expected_fragment) -> None:
    """apply_project must return valid=False cleanly, not raise an exception."""
    project = _make_every_project(tmp_path, every_value)
    crontab = tmp_path / "crontab.txt"
    crontab.write_text("", encoding="utf-8")
    result = apply_project(
        project,
        backend="cron",
        platform="linux",
        crontab_path=crontab,
        manage_crontab=True,
    )
    assert result.valid is False
    assert not crontab.read_text(), "crontab must not be written for an incompatible schedule"

from __future__ import annotations

import textwrap

from libs.actions.plan_project import plan_project
from libs.actions.validate_project import validate_project
from libs.domain import DeployedJobState, ProjectState
from libs.services.state_store import save_project_state


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

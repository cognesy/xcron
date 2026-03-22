from __future__ import annotations

import textwrap

from libs.actions.apply_project import apply_project
from libs.actions.plan_project import plan_project
from libs.services.backends.cron_service import apply_cron_plan, inspect_cron_project, prune_cron_project


def test_cron_backend_apply_inspect_and_prune(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: cron-demo
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: enabled_job
                schedule:
                  cron: "*/5 * * * *"
                command: echo enabled
              - id: disabled_job
                enabled: false
                schedule:
                  cron: "0 * * * *"
                command: echo disabled
            """
        ),
        encoding="utf-8",
    )

    state_root = tmp_path / "state-root"
    crontab_path = tmp_path / "crontab.txt"
    crontab_path.write_text("# unmanaged\nMAILTO=user@example.com\n", encoding="utf-8")

    plan = plan_project(project, backend="cron", state_root=state_root, platform="linux")
    state = apply_cron_plan(plan, state_root=state_root, crontab_path=crontab_path, manage_crontab=True)
    content = crontab_path.read_text(encoding="utf-8")
    inspections = inspect_cron_project("cron-demo", crontab_path=crontab_path)

    assert [job.qualified_id for job in state.jobs] == ["cron-demo.disabled_job", "cron-demo.enabled_job"]
    assert all(job.stdout_log_path for job in state.jobs)
    assert all(job.stderr_log_path for job in state.jobs)
    assert "# unmanaged" in content
    assert "MAILTO=user@example.com" in content
    assert [(item.qualified_id, item.enabled) for item in inspections] == [
        ("cron-demo.disabled_job", False),
        ("cron-demo.enabled_job", True),
    ]
    assert all(item.artifact_path == str(crontab_path) for item in inspections)
    assert all(item.stdout_log_path.name.endswith(".out.log") for item in inspections)
    assert all(item.stderr_log_path.name.endswith(".err.log") for item in inspections)

    removed = prune_cron_project("cron-demo", crontab_path=crontab_path, manage_crontab=True)
    pruned_content = crontab_path.read_text(encoding="utf-8")

    assert len(removed) == 2
    assert "# unmanaged" in pruned_content
    assert "BEGIN XCRON project=cron-demo" not in pruned_content


def test_apply_project_repairs_missing_actual_cron_block(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "jobs.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: demo.project
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: sync_job
                schedule:
                  cron: "*/5 * * * *"
                command: echo synced
            """
        ),
        encoding="utf-8",
    )

    state_root = tmp_path / "state-root"
    crontab_path = tmp_path / "crontab.txt"
    crontab_path.write_text("# unmanaged\n", encoding="utf-8")

    first = apply_project(
        project,
        schedule_name="jobs",
        backend="cron",
        state_root=state_root,
        crontab_path=crontab_path,
        manage_crontab=True,
    )
    assert first.valid is True

    crontab_path.write_text("# unmanaged\n", encoding="utf-8")

    second = apply_project(
        project,
        schedule_name="jobs",
        backend="cron",
        state_root=state_root,
        crontab_path=crontab_path,
        manage_crontab=True,
    )
    inspections = inspect_cron_project("demo.project", crontab_path=crontab_path)

    assert second.valid is True
    assert "BEGIN XCRON project=demo.project" in crontab_path.read_text(encoding="utf-8")
    assert inspections[0].job_id == "sync_job"
    assert inspections[0].stdout_log_path.name == "demo.project.sync_job.out.log"
    assert inspections[0].stderr_log_path.name == "demo.project.sync_job.err.log"

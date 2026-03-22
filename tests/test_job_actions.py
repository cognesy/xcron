from __future__ import annotations

import textwrap

from libs.actions import add_job, disable_job, list_jobs, remove_job, show_job, update_job


def test_job_actions_cover_list_show_add_update_disable_and_remove(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "scripts").mkdir()
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
              - id: sync_docs
                schedule:
                  cron: "*/15 * * * *"
                command: ./scripts/sync-docs
            """
        ),
        encoding="utf-8",
    )

    listed = list_jobs(project)
    assert listed.valid is True
    assert [job.job_id for job in listed.jobs] == ["sync_docs"]

    shown = show_job("sync_docs", project)
    assert shown.valid is True
    assert shown.job is not None
    assert shown.job.execution.command == "./scripts/sync-docs"
    assert shown.raw_job is not None
    assert shown.raw_job["id"] == "sync_docs"

    added = add_job(
        {
            "id": "cleanup_tmp",
            "schedule": {"every": "1h"},
            "command": "./scripts/cleanup-tmp",
            "working_dir": ".",
        },
        project,
    )
    assert added.valid is True
    assert added.job is not None
    assert added.job.job_id == "cleanup_tmp"

    updated = update_job(
        "cleanup_tmp",
        project,
        updates={
            "command": "./scripts/cleanup-tmp --deep",
            "schedule": {"cron": "0 * * * *"},
            "env": {"MODE": "deep"},
        },
    )
    assert updated.valid is True
    assert updated.job is not None
    assert updated.job.execution.command == "./scripts/cleanup-tmp --deep"
    assert updated.raw_job is not None
    assert updated.raw_job["env"] == {"MODE": "deep"}

    disabled = disable_job("cleanup_tmp", project)
    assert disabled.valid is True
    assert disabled.job is not None
    assert disabled.job.enabled is False

    removed = remove_job("cleanup_tmp", project)
    assert removed.valid is True
    assert removed.removed_job_identifier == "cleanup_tmp"

    final_list = list_jobs(project)
    assert final_list.valid is True
    assert [job.job_id for job in final_list.jobs] == ["sync_docs"]


def test_job_actions_return_clean_error_on_invalid_mutation(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "scripts").mkdir()
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
              - id: sync_docs
                schedule:
                  cron: "*/15 * * * *"
                command: ./scripts/sync-docs
            """
        ),
        encoding="utf-8",
    )

    result = update_job(
        "sync_docs",
        project,
        updates={"working_dir": "./missing-dir"},
    )

    assert result.valid is False
    assert result.error is not None
    assert "working directory does not exist" in result.error

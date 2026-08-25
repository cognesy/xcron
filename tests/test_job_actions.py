from __future__ import annotations

import textwrap

from xcron.sdk import JobCreateRequest, JobUpdateRequest, ScheduleRequest, Xcron


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

    with Xcron.open(project, backend="cron", platform="linux") as client:
        listed = client.jobs.list()
        shown = client.jobs.show("sync_docs")
        added = client.jobs.add(
            JobCreateRequest(
                job_id="cleanup_tmp",
                schedule=ScheduleRequest.every("1h"),
                command="./scripts/cleanup-tmp",
                working_dir=".",
            )
        )
        updated = client.jobs.update(
            "cleanup_tmp",
            JobUpdateRequest(
                command="./scripts/cleanup-tmp --deep",
                schedule=ScheduleRequest.cron("0 * * * *"),
                env={"MODE": "deep"},
            ),
        )
        disabled = client.jobs.disable("cleanup_tmp")
        removed = client.jobs.remove("cleanup_tmp")
        final_list = client.jobs.list()

    assert listed.valid is True
    assert [job.job_id for job in listed.jobs] == ["sync_docs"]
    assert shown.valid is True
    assert shown.job is not None
    assert shown.job.execution.command == "./scripts/sync-docs"
    assert shown.raw_job is not None
    assert shown.raw_job["id"] == "sync_docs"
    assert added.valid is True
    assert added.job is not None
    assert added.job.job_id == "cleanup_tmp"
    assert updated.valid is True
    assert updated.job is not None
    assert updated.job.execution.command == "./scripts/cleanup-tmp --deep"
    assert updated.raw_job is not None
    assert updated.raw_job["env"] == {"MODE": "deep"}
    assert disabled.valid is True
    assert disabled.job is not None
    assert disabled.job.enabled is False
    assert removed.valid is True
    assert removed.removed_job_identifier == "cleanup_tmp"
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

    with Xcron.open(project, backend="cron", platform="linux") as client:
        result = client.jobs.update("sync_docs", JobUpdateRequest(working_dir="./missing-dir"))

    assert result.valid is False
    assert result.error is not None
    assert "working directory does not exist" in result.error

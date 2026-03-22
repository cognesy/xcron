from __future__ import annotations

import textwrap

import pytest

from libs.services import (
    ManifestEditValidationError,
    add_manifest_job,
    get_manifest_job,
    list_manifest_jobs,
    remove_manifest_job,
    set_manifest_job_enabled,
    update_manifest_job,
)


def test_manifest_editor_supports_job_crud_and_enable_disable(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "scripts").mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    manifest_path = schedule_dir / "default.yaml"
    manifest_path.write_text(
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

    assert [job["id"] for job in list_manifest_jobs(project)] == ["sync_docs"]

    added = add_manifest_job(
        {
            "id": "cleanup_tmp",
            "enabled": True,
            "schedule": {"every": "1h"},
            "command": "./scripts/cleanup-tmp",
            "working_dir": ".",
            "overlap": "forbid",
        },
        project,
    )
    assert added.job_data is not None
    assert added.job_data["id"] == "cleanup_tmp"
    assert [job["id"] for job in list_manifest_jobs(project)] == ["sync_docs", "cleanup_tmp"]

    shown = get_manifest_job("demo-app.cleanup_tmp", project)
    assert shown["command"] == "./scripts/cleanup-tmp"
    assert shown["schedule"] == {"every": "1h"}

    updated = update_manifest_job(
        "cleanup_tmp",
        updates={
            "command": "./scripts/cleanup-tmp --deep",
            "schedule": {"cron": "0 * * * *"},
            "description": "Cleans temp files",
            "env": {"MODE": "deep"},
        },
        project_path=project,
    )
    assert updated.job_data is not None
    assert updated.job_data["command"] == "./scripts/cleanup-tmp --deep"
    assert updated.job_data["schedule"] == {"cron": "0 * * * *"}

    disabled = set_manifest_job_enabled("cleanup_tmp", False, project)
    assert disabled.job_data is not None
    assert disabled.job_data["enabled"] is False

    cleared = update_manifest_job(
        "cleanup_tmp",
        updates={"command": "./scripts/cleanup-tmp --final"},
        clear_fields=("description", "env"),
        project_path=project,
    )
    assert cleared.job_data is not None
    assert "description" not in cleared.job_data
    assert "env" not in cleared.job_data

    removed = remove_manifest_job("cleanup_tmp", project)
    assert removed.job_data is None
    assert [job["id"] for job in list_manifest_jobs(project)] == ["sync_docs"]
    assert "cleanup_tmp" not in manifest_path.read_text(encoding="utf-8")


def test_manifest_editor_does_not_commit_invalid_mutation(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "scripts").mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    manifest_path = schedule_dir / "default.yaml"
    original_text = textwrap.dedent(
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
    )
    manifest_path.write_text(original_text, encoding="utf-8")

    with pytest.raises(ManifestEditValidationError):
        update_manifest_job(
            "sync_docs",
            updates={"working_dir": "./missing-dir"},
            project_path=project,
        )

    assert manifest_path.read_text(encoding="utf-8") == original_text

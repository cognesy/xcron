from __future__ import annotations

import textwrap

from libs.actions.validate_project import validate_project


def test_validate_project_success_and_hash_determinism(tmp_path) -> None:
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
              timezone: Europe/Warsaw
            jobs:
              - id: sync_docs
                schedule:
                  cron: "*/15 * * * *"
                command: ./scripts/sync-docs
                overlap: forbid
            """
        ),
        encoding="utf-8",
    )

    first = validate_project(project)
    second = validate_project(project)

    assert first.valid is True
    assert second.valid is True
    assert first.hashes is not None
    assert second.hashes is not None
    assert first.hashes.manifest_hash == second.hashes.manifest_hash
    assert first.hashes.job_hashes == second.hashes.job_hashes
    assert first.normalized_manifest is not None
    assert [job.qualified_id for job in first.normalized_manifest.jobs] == ["demo-app.sync_docs"]


def test_validate_project_reports_schema_error(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        "version: 1\nproject: {}\njobs: []\n",
        encoding="utf-8",
    )

    result = validate_project(project)

    assert result.valid is False
    assert result.errors
    assert result.errors[0].path == "/project"


def test_validate_project_requires_schedule_selection_when_multiple_manifests_exist(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    for name in ("main", "ops"):
        (schedule_dir / f"{name}.yaml").write_text(
            textwrap.dedent(
                f"""\
                version: 1
                project:
                  id: demo-app
                jobs:
                  - id: {name}
                    schedule:
                      cron: "0 * * * *"
                    command: echo {name}
                """
            ),
            encoding="utf-8",
        )

    result = validate_project(project)

    assert result.valid is False
    assert result.errors
    assert "--schedule" in result.errors[0].message

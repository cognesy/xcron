from __future__ import annotations

import textwrap

import pytest

from apps.cli.main import build_parser, main


def test_cli_help_covers_root_group_and_leaf_commands(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as root_exit:
        parser.parse_args(["--help"])
    assert root_exit.value.code == 0
    root_help = capsys.readouterr().out
    assert "jobs" in root_help
    assert "edit jobs inside one schedule manifest" in root_help

    with pytest.raises(SystemExit) as group_exit:
        parser.parse_args(["jobs", "--help"])
    assert group_exit.value.code == 0
    group_help = capsys.readouterr().out
    assert "add" in group_help
    assert "update" in group_help
    assert "edit YAML only" in group_help

    with pytest.raises(SystemExit) as leaf_exit:
        parser.parse_args(["jobs", "add", "--help"])
    assert leaf_exit.value.code == 0
    leaf_help = capsys.readouterr().out
    assert "--command" in leaf_help
    assert "--cron" in leaf_help
    assert "--every" in leaf_help


def test_jobs_cli_executes_representative_manifest_flow(tmp_path, capsys) -> None:
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

    assert main(["--project", str(project), "jobs", "add", "cleanup_tmp", "--command", "./scripts/cleanup-tmp", "--every", "1h"]) == 0
    add_output = capsys.readouterr().out
    assert "added_job: demo-app.cleanup_tmp" in add_output

    assert main(["--project", str(project), "jobs", "list"]) == 0
    list_output = capsys.readouterr().out
    assert "sync_docs" in list_output
    assert "cleanup_tmp" in list_output

    assert main(["--project", str(project), "jobs", "show", "cleanup_tmp"]) == 0
    show_output = capsys.readouterr().out
    assert "job: demo-app.cleanup_tmp" in show_output
    assert "schedule: every=1h" in show_output

    assert main(["--project", str(project), "jobs", "update", "cleanup_tmp", "--cron", "0 * * * *", "--clear-env"]) == 0
    update_output = capsys.readouterr().out
    assert "updated_job: demo-app.cleanup_tmp" in update_output

    assert main(["--project", str(project), "jobs", "disable", "cleanup_tmp"]) == 0
    disable_output = capsys.readouterr().out
    assert "disabled_job: demo-app.cleanup_tmp" in disable_output

    assert main(["--project", str(project), "jobs", "remove", "cleanup_tmp"]) == 0
    remove_output = capsys.readouterr().out
    assert "removed_job: cleanup_tmp" in remove_output

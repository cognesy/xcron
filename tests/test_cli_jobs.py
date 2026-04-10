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
    assert "Authoritative runtime help for xcron lives under `resources/help/`." in root_help

    with pytest.raises(SystemExit) as group_exit:
        parser.parse_args(["jobs", "--help"])
    assert group_exit.value.code == 0
    group_help = capsys.readouterr().out
    assert "add" in group_help
    assert "update" in group_help
    assert "edit YAML only" in group_help
    assert "These commands edit YAML only; use `xcron apply`" in group_help

    with pytest.raises(SystemExit) as leaf_exit:
        parser.parse_args(["jobs", "add", "--help"])
    assert leaf_exit.value.code == 0
    leaf_help = capsys.readouterr().out
    assert "--command" in leaf_help
    assert "--cron" in leaf_help
    assert "--every" in leaf_help
    assert "Create a new manifest job." in leaf_help


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
    assert "kind: jobs.add" in add_output
    assert "target: demo-app.cleanup_tmp" in add_output
    assert "outcome: added" in add_output

    assert main(["--project", str(project), "jobs", "list"]) == 0
    list_output = capsys.readouterr().out
    assert "count: 2 of 2" in list_output
    assert "jobs[2,]{job_id,enabled,schedule,command}:" in list_output
    assert "sync_docs,true,cron=*/15 * * * *,./scripts/sync-docs" in list_output
    assert "cleanup_tmp,true,every=1h,./scripts/cleanup-tmp" in list_output

    assert main(["--project", str(project), "jobs", "show", "cleanup_tmp"]) == 0
    show_output = capsys.readouterr().out
    assert "job: demo-app.cleanup_tmp" in show_output
    assert "schedule: every=1h" in show_output

    assert main(["--project", str(project), "jobs", "update", "cleanup_tmp", "--cron", "0 * * * *", "--clear-env"]) == 0
    update_output = capsys.readouterr().out
    assert "kind: jobs.update" in update_output
    assert "target: demo-app.cleanup_tmp" in update_output
    assert "outcome: updated" in update_output

    assert main(["--project", str(project), "jobs", "disable", "cleanup_tmp"]) == 0
    disable_output = capsys.readouterr().out
    assert "kind: jobs.disable" in disable_output
    assert "outcome: disabled" in disable_output

    assert main(["--project", str(project), "jobs", "remove", "cleanup_tmp"]) == 0
    remove_output = capsys.readouterr().out
    assert "kind: jobs.remove" in remove_output
    assert "target: cleanup_tmp" in remove_output
    assert "outcome: removed" in remove_output


def test_jobs_cli_rejects_malformed_env_without_traceback(tmp_path, capsys) -> None:
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

    assert (
        main(
            [
                "--project",
                str(project),
                "jobs",
                "add",
                "cleanup_tmp",
                "--command",
                "./scripts/cleanup-tmp",
                "--every",
                "1h",
                "--env",
                "BAD",
            ]
        )
        == 2
    )
    output = capsys.readouterr()
    assert "invalid env assignment, expected KEY=VALUE: BAD" in output.out
    assert "Traceback" not in output.out
    assert "Traceback" not in output.err


def test_jobs_cli_rejects_no_op_update_without_rewriting_manifest(tmp_path, capsys) -> None:
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

    assert main(["--project", str(project), "jobs", "update", "sync_docs"]) == 2
    output = capsys.readouterr()
    assert "at least one update field or clear flag is required" in output.out
    assert manifest_path.read_text(encoding="utf-8") == original_text


def test_jobs_enable_reports_noop_when_job_is_already_enabled(tmp_path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    manifest_path = schedule_dir / "default.yaml"
    manifest_text = textwrap.dedent(
        """\
        version: 1
        project:
          id: demo-app
        defaults:
          working_dir: .
          shell: /bin/sh
        jobs:
          - id: sync_docs
            enabled: true
            schedule:
              cron: "*/15 * * * *"
            command: ./scripts/sync-docs
        """
    )
    manifest_path.write_text(manifest_text, encoding="utf-8")

    assert main(["--project", str(project), "jobs", "enable", "sync_docs"]) == 0
    output = capsys.readouterr().out

    assert "kind: jobs.enable" in output
    assert "outcome: noop" in output
    assert manifest_path.read_text(encoding="utf-8") == manifest_text

from __future__ import annotations

import os
import textwrap

from typer.testing import CliRunner

from apps.cli.typer_app import app


runner = CliRunner()


def _make_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: typer-demo
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
    return project


def test_typer_validate_command_uses_existing_action_and_output_contract(tmp_path) -> None:
    project = _make_project(tmp_path)

    result = runner.invoke(app, ["validate", "--project", str(project)])

    assert result.exit_code == 0
    assert "project:" in result.stdout
    assert "manifest_hash:" in result.stdout


def test_typer_plan_command_uses_existing_action_and_output_contract(tmp_path) -> None:
    project = _make_project(tmp_path)

    result = runner.invoke(app, ["plan", "--project", str(project)])

    assert result.exit_code == 0
    assert "backend:" in result.stdout
    assert "changes[1,]{kind,id,reason}:" in result.stdout


def test_typer_status_and_inspect_commands_use_existing_action_and_output_contract(tmp_path, monkeypatch) -> None:
    project = _make_project(tmp_path)
    crontab_path = tmp_path / "crontab.txt"
    crontab_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("XCRON_CRONTAB_PATH", str(crontab_path))

    status_result = runner.invoke(app, ["status", "--project", str(project), "--backend", "cron"])
    inspect_result = runner.invoke(app, ["inspect", "sync_docs", "--project", str(project), "--backend", "cron"])

    assert status_result.exit_code == 0
    assert "statuses" in status_result.stdout
    assert inspect_result.exit_code == 0
    assert "desired:" in inspect_result.stdout


def test_typer_jobs_and_apply_commands_use_existing_action_and_output_contract(tmp_path, monkeypatch) -> None:
    project = _make_project(tmp_path)
    state_root = tmp_path / "state-root"
    crontab_path = tmp_path / "crontab.txt"
    crontab_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))
    monkeypatch.setenv("XCRON_CRONTAB_PATH", str(crontab_path))

    add_result = runner.invoke(
        app,
        [
            "jobs",
            "add",
            "cleanup_tmp",
            "--project",
            str(project),
            "--command",
            "./scripts/cleanup-tmp",
            "--every",
            "1h",
        ],
    )
    apply_result = runner.invoke(app, ["apply", "--project", str(project), "--backend", "cron"])

    assert add_result.exit_code == 0
    assert "kind: jobs.add" in add_result.stdout
    assert apply_result.exit_code == 0
    assert "kind: apply" in apply_result.stdout


def test_typer_hooks_commands_report_repo_local_hook_state(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    executable = tmp_path / "bin" / "xcron"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    monkeypatch.setenv("PATH", f"{executable.parent}:{os.environ.get('PATH', '')}")

    with runner.isolated_filesystem(temp_dir=str(project)):
        install_result = runner.invoke(app, ["hooks", "install"])
        status_result = runner.invoke(app, ["hooks", "status"])

    assert install_result.exit_code == 0
    assert "kind: hooks.install" in install_result.stdout
    assert status_result.exit_code == 0
    assert "kind: hooks.status" in status_result.stdout


def test_typer_help_uses_authored_resources_help_content() -> None:
    root_help = runner.invoke(app, ["--help"])
    jobs_help = runner.invoke(app, ["jobs", "--help"])
    add_help = runner.invoke(app, ["jobs", "add", "--help"])

    assert root_help.exit_code == 0
    assert "Authoritative runtime help for xcron lives under resources/help/." in root_help.stdout
    assert jobs_help.exit_code == 0
    assert "These commands edit YAML only; use xcron apply to reconcile backend state" in jobs_help.stdout
    assert add_help.exit_code == 0
    assert "Create a new manifest job." in add_help.stdout

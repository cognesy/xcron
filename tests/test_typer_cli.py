from __future__ import annotations

import json
import os
import textwrap
from importlib.metadata import PackageNotFoundError, version as distribution_version

from typer.testing import CliRunner

from xcron_cli.typer_app import app


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


def test_version_is_a_project_and_backend_free_liveness_probe(monkeypatch) -> None:
    def fail_if_opened(*args, **kwargs):
        raise AssertionError("--version must not open the SDK or scheduler")

    monkeypatch.setattr("xcron_cli.typer_app._open_client", fail_if_opened)

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout == f"xcron {distribution_version('xcron')}\n"


def test_version_survives_missing_distribution_metadata(monkeypatch) -> None:
    def missing_distribution(_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr("xcron_cli.typer_app.distribution_version", missing_distribution)

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout == "xcron unknown\n"


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


def test_unknown_backend_is_a_structured_usage_error(tmp_path) -> None:
    project = _make_project(tmp_path)
    structured_runner = CliRunner(mix_stderr=False)

    result = structured_runner.invoke(
        app,
        ["plan", "--project", str(project), "--backend", "bogus", "--output", "json"],
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout) == {
        "code": "usage_error",
        "details": [],
        "help": [],
        "kind": "error",
        "message": "unsupported scheduler backend: bogus (available: cron, launchd)",
    }
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


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

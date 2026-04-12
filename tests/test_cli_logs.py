"""Tests for xcron logs list and logs clear commands."""

from __future__ import annotations

import json
import textwrap

from apps.cli.main import main
from libs.actions.apply_project import apply_project


MANIFEST_YAML = textwrap.dedent(
    """\
    version: 1
    project:
      id: logs-demo
    defaults:
      working_dir: .
      shell: /bin/sh
    jobs:
      - id: hello
        schedule:
          cron: "*/5 * * * *"
        command: echo hello
      - id: world
        schedule:
          cron: "0 * * * *"
        command: echo world
    """
)


def _setup_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(MANIFEST_YAML, encoding="utf-8")

    state_root = tmp_path / "state-root"
    crontab_path = tmp_path / "crontab.txt"
    crontab_path.write_text("", encoding="utf-8")

    result = apply_project(
        project,
        backend="cron",
        state_root=state_root,
        crontab_path=crontab_path,
        manage_crontab=True,
    )
    assert result.valid is True

    # Write some content to log files so they exist and have size
    logs_dir = state_root / "projects" / "logs-demo" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "logs-demo.hello.out.log").write_text("hello stdout\n", encoding="utf-8")
    (logs_dir / "logs-demo.hello.err.log").write_text("hello stderr\n", encoding="utf-8")
    (logs_dir / "logs-demo.world.out.log").write_text("world stdout output\n", encoding="utf-8")

    return project, state_root, crontab_path


def test_logs_list_shows_existing_files(tmp_path, monkeypatch, capsys) -> None:
    project, state_root, _ = _setup_project(tmp_path)
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))

    assert main(["logs", "list", "--project", str(project)]) == 0
    captured = capsys.readouterr()

    assert "logs-demo" in captured.out
    assert "3 of 3" in captured.out
    assert "hello" in captured.out
    assert "stdout" in captured.out


def test_logs_list_json_output(tmp_path, monkeypatch, capsys) -> None:
    project, state_root, _ = _setup_project(tmp_path)
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))

    assert main(["logs", "list", "--project", str(project), "--output", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["project"] == "logs-demo"
    assert len(payload["files"]) == 3
    assert all("job" in f and "kind" in f and "path" in f and "size" in f for f in payload["files"])


def test_logs_list_with_job_filter(tmp_path, monkeypatch, capsys) -> None:
    project, state_root, _ = _setup_project(tmp_path)
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))

    assert main(["logs", "list", "--project", str(project), "--job", "hello"]) == 0
    captured = capsys.readouterr()

    assert "2 of 2" in captured.out
    assert "hello" in captured.out


def test_logs_list_tmux_output(tmp_path, monkeypatch, capsys) -> None:
    project, state_root, _ = _setup_project(tmp_path)
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))

    assert main(["logs", "list", "--project", str(project), "--output", "tmux"]) == 0
    captured = capsys.readouterr()

    assert "project: logs-demo" in captured.out
    assert "files[3]:" in captured.out


def test_logs_clear_dry_run_does_not_delete(tmp_path, monkeypatch, capsys) -> None:
    project, state_root, _ = _setup_project(tmp_path)
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))

    logs_dir = state_root / "projects" / "logs-demo" / "logs"
    original_content = (logs_dir / "logs-demo.hello.out.log").read_text()

    assert main(["logs", "clear", "--project", str(project)]) == 0
    captured = capsys.readouterr()

    assert "dry_run" in captured.out
    # File should still have original content
    assert (logs_dir / "logs-demo.hello.out.log").read_text() == original_content


def test_logs_clear_with_apply_truncates_files(tmp_path, monkeypatch, capsys) -> None:
    project, state_root, _ = _setup_project(tmp_path)
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))

    logs_dir = state_root / "projects" / "logs-demo" / "logs"
    assert (logs_dir / "logs-demo.hello.out.log").read_text() != ""

    assert main(["logs", "clear", "--project", str(project), "--apply"]) == 0
    captured = capsys.readouterr()

    assert "cleared" in captured.out
    # Files should be truncated
    assert (logs_dir / "logs-demo.hello.out.log").read_text() == ""
    assert (logs_dir / "logs-demo.hello.err.log").read_text() == ""
    assert (logs_dir / "logs-demo.world.out.log").read_text() == ""


def test_logs_clear_json_output(tmp_path, monkeypatch, capsys) -> None:
    project, state_root, _ = _setup_project(tmp_path)
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))

    assert main(["logs", "clear", "--project", str(project), "--apply", "--output", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["project"] == "logs-demo"
    assert payload["dry_run"] is False
    assert payload["cleared"] == 3
    assert len(payload["files"]) == 3


def test_logs_clear_with_job_filter(tmp_path, monkeypatch, capsys) -> None:
    project, state_root, _ = _setup_project(tmp_path)
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))

    logs_dir = state_root / "projects" / "logs-demo" / "logs"

    assert main(["logs", "clear", "--project", str(project), "--apply", "--job", "hello"]) == 0

    # hello logs should be cleared
    assert (logs_dir / "logs-demo.hello.out.log").read_text() == ""
    assert (logs_dir / "logs-demo.hello.err.log").read_text() == ""
    # world log should be untouched
    assert (logs_dir / "logs-demo.world.out.log").read_text() == "world stdout output\n"


def test_logs_list_no_logs_exist(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(MANIFEST_YAML, encoding="utf-8")

    state_root = tmp_path / "state-root"
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))

    assert main(["logs", "list", "--project", str(project)]) == 0
    captured = capsys.readouterr()

    assert "0 of 0" in captured.out

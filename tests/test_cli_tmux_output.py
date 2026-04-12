"""Tests for --output tmux across CLI commands."""

from __future__ import annotations

import textwrap

from apps.cli.main import main
from libs.actions.apply_project import apply_project


def test_status_tmux_output_is_compact(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: tmux-demo
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: ping_job
                schedule:
                  cron: "*/5 * * * *"
                command: echo ping
              - id: paused_job
                enabled: false
                schedule:
                  cron: "0 * * * *"
                command: echo paused
            """
        ),
        encoding="utf-8",
    )

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

    monkeypatch.setenv("XCRON_CRONTAB_PATH", str(crontab_path))
    assert main(["status", "--project", str(project), "--backend", "cron", "--output", "tmux"]) == 0
    captured = capsys.readouterr()

    assert "backend: cron" in captured.out
    assert "statuses[2]:" in captured.out
    assert "ok" in captured.out
    assert "tmux-demo.ping_job" in captured.out
    assert "disabled" in captured.out
    assert "tmux-demo.paused_job" in captured.out
    # tmux output should NOT contain toon-style headers like "statuses[2,]{kind,id,reason}:"
    assert "{kind,id,reason}" not in captured.out


def test_plan_tmux_output(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: tmux-plan
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: hello
                schedule:
                  cron: "*/5 * * * *"
                command: echo hello
            """
        ),
        encoding="utf-8",
    )

    state_root = tmp_path / "state-root"
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))
    assert main(["plan", "--project", str(project), "--backend", "cron", "--output", "tmux"]) == 0
    captured = capsys.readouterr()

    assert "backend: cron" in captured.out
    assert "changes[1]:" in captured.out
    assert "create" in captured.out

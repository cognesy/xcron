from __future__ import annotations

import os

from xcron.channels.cli.main import main


def test_hooks_status_and_repair_report_repo_local_hook_state(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    executable = tmp_path / "bin" / "xcron"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{executable.parent}:{os.environ.get('PATH', '')}")
    monkeypatch.chdir(project)

    assert main(["hooks", "repair"]) == 0
    repair_output = capsys.readouterr().out
    assert "kind: hooks.install" in repair_output

    assert main(["hooks", "status"]) == 0
    status_output = capsys.readouterr().out
    assert "kind: hooks.status" in status_output
    assert "codex:" in status_output
    assert "claude:" in status_output


def test_hooks_status_reports_missing_executable_as_structured_error(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv("PATH", "")

    assert main(["hooks", "status", "--output", "json"]) == 1
    output = capsys.readouterr().out
    assert '"kind": "error"' in output
    assert "unable to resolve xcron executable" in output


def test_hidden_session_start_uses_sdk_hook_resolution(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        """version: 1\nproject:\n  id: hook-start\ndefaults:\n  working_dir: .\n  shell: /bin/sh\njobs: []\n""",
        encoding="utf-8",
    )
    executable = tmp_path / "bin" / "xcron"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(executable.parent))
    monkeypatch.chdir(project)

    assert main(["hooks", "session-start", "--output", "json"]) == 0
    assert '"project"' in capsys.readouterr().out

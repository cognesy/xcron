from __future__ import annotations

import os

from apps.cli.main import main


def test_hooks_status_and_repair_report_repo_local_hook_state(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    executable = tmp_path / "bin" / "xcron"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
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

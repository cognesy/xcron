from __future__ import annotations

import argparse
import textwrap

from apps.cli.commands import inspect
from libs.actions.apply_project import apply_project


def test_inspect_prints_artifact_wrapper_and_log_paths_for_cron(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: inspect-demo
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: ping_job
                schedule:
                  cron: "*/5 * * * *"
                command: echo ping
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
    exit_code = inspect.handle(
        argparse.Namespace(
            job_id="ping_job",
            project=str(project),
            schedule=None,
            backend="cron",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "desired:" in captured.out
    assert "  qualified_id: inspect-demo.ping_job" in captured.out
    assert "  command: echo ping" in captured.out
    assert "  working_dir:" in captured.out
    assert "deployed:" in captured.out
    assert f"artifact_path: {crontab_path}" in captured.out
    assert "wrapper_path:" in captured.out
    assert "stdout_log:" in captured.out
    assert "stderr_log:" in captured.out
    assert "raw_entry:" in captured.out

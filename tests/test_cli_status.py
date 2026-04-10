from __future__ import annotations

import argparse
import textwrap

from apps.cli.commands import status
from libs.actions.apply_project import apply_project
from tests.cli_assertions import assert_list_output


def test_status_prints_operator_facing_states_for_cron(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: status-demo
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
    exit_code = status.handle(
        argparse.Namespace(
            project=str(project),
            schedule=None,
            backend="cron",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "backend: cron" in captured.out
    assert_list_output(captured.out, count="2 of 2", header="statuses[2,]{kind,id,reason}:")
    assert "ok,status-demo.ping_job,desired definition and actual backend state are aligned" in captured.out
    assert "disabled,status-demo.paused_job,job is disabled in desired state" in captured.out

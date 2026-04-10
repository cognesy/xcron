from __future__ import annotations

import json
import textwrap

from apps.cli.main import main
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
    assert main(["status", "--project", str(project), "--backend", "cron"]) == 0
    captured = capsys.readouterr()

    assert "backend: cron" in captured.out
    assert_list_output(captured.out, count="2 of 2", header="statuses[2,]{kind,id,reason}:")
    assert "ok,status-demo.ping_job,desired definition and actual backend state are aligned" in captured.out
    assert "disabled,status-demo.paused_job,job is disabled in desired state" in captured.out


def test_status_supports_json_output_format_for_jq_style_consumers(tmp_path, monkeypatch, capsys) -> None:
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
    assert main(["status", "--project", str(project), "--backend", "cron", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["backend"] == "cron"
    assert payload["count"] == "1 of 1"
    assert payload["statuses"] == [
        {
            "id": "status-demo.ping_job",
            "kind": "ok",
            "reason": "desired definition and actual backend state are aligned",
        }
    ]

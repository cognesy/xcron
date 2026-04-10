from __future__ import annotations

import json
import textwrap

from apps.cli.main import main


def test_bare_xcron_returns_content_first_home_view(tmp_path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: demo-home
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

    assert main(["--project", str(project)]) == 0
    output = capsys.readouterr().out

    assert "description: Manage project-local schedules against native OS schedulers" in output
    assert "project:" in output
    assert "backend:" in output
    assert "jobs:" in output
    assert "plan_summary[1,]{kind,count}:" in output


def test_bare_xcron_supports_json_output_format(tmp_path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: demo-home
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

    assert main(["--project", str(project), "--output", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["backend"] in {"cron", "launchd"}
    assert payload["jobs"]["total"] == 1
    assert payload["plan_summary"] == [{"count": 1, "kind": "create"}]

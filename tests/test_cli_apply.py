from __future__ import annotations

import textwrap

from apps.cli.main import main
from tests.cli_assertions import assert_mutation_output


def test_apply_reports_noop_when_backend_is_already_converged(tmp_path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: apply-demo
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

    state_root = tmp_path / "state-root"
    crontab_path = tmp_path / "crontab.txt"
    crontab_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))
    monkeypatch.setenv("XCRON_CRONTAB_PATH", str(crontab_path))

    assert main(["--project", str(project), "--backend", "cron", "apply"]) == 0
    capsys.readouterr()

    assert main(["--project", str(project), "--backend", "cron", "apply"]) == 0
    output = capsys.readouterr().out

    assert_mutation_output(output, kind="apply", outcome="noop")

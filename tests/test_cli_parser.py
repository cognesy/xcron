from __future__ import annotations

import json

from typer.testing import CliRunner

from xcron.channels.cli.main import main
from xcron.channels.cli.typer_app import app
from tests.cli_assertions import assert_usage_error


runner = CliRunner()


def _make_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        """\
version: 1
project:
  id: parser-demo
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: sync_docs
    schedule:
      cron: "*/15 * * * *"
    command: ./scripts/sync-docs
""",
        encoding="utf-8",
    )
    return project


def test_parser_usage_errors_exit_two_and_keep_stdout_clean() -> None:
    """The argument parser's own message is diagnostic text, so it goes to stderr.

    xcron's *structured* usage errors still go to stdout — the three tests
    below pin that. This one covers the case xcron never got to render: click
    rejected the arguments before any command ran, so there is no payload to
    put on stdout and a caller parsing it must not find prose there.
    """
    result = runner.invoke(app, ["jobs", "add"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Usage:" in result.stderr
    assert "Error" in result.stderr


def test_invalid_top_level_fields_return_structured_usage_error(tmp_path, capsys) -> None:
    project = _make_project(tmp_path)

    assert main(["--project", str(project), "status", "--fields", "backend,missing_field"]) == 2
    captured = capsys.readouterr()

    assert_usage_error(captured.out, message_fragment="unknown field selection:")
    assert "missing_field" in captured.out


def test_invalid_nested_fields_return_structured_usage_error(tmp_path, capsys) -> None:
    project = _make_project(tmp_path)

    assert main(["--project", str(project), "inspect", "sync_docs", "--fields", "desired.fake_field"]) == 2
    captured = capsys.readouterr()

    assert_usage_error(captured.out)
    assert "desired.fake_field" in captured.out


def test_invalid_field_selection_respects_json_output_format(tmp_path, capsys) -> None:
    project = _make_project(tmp_path)

    assert main(["--project", str(project), "status", "--output", "json", "--fields", "backend,missing_field"]) == 2
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "error"
    assert payload["code"] == "usage_error"
    assert "missing_field" in payload["message"]

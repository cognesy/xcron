from __future__ import annotations

import pytest

from apps.cli.main import build_parser, main
from tests.cli_assertions import assert_usage_error


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


def test_parser_usage_errors_are_rendered_to_stdout_in_structured_form(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["jobs", "add"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert_usage_error(captured.out)
    assert "message:" in captured.out
    assert "Run `xcron jobs add --help` to see available commands" in captured.out
    assert captured.err == ""


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

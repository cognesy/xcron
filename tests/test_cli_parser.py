from __future__ import annotations

import pytest

from apps.cli.main import build_parser


def test_parser_usage_errors_are_rendered_to_stdout_in_structured_form(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["jobs", "add"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "kind: error" in captured.out
    assert "code: usage_error" in captured.out
    assert "message:" in captured.out
    assert "Run `xcron jobs add --help` to see available commands" in captured.out
    assert captured.err == ""

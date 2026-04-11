from __future__ import annotations

import json
import textwrap

import structlog
from typer.testing import CliRunner

from apps.cli.typer_app import app
from libs.services.logging_config import load_logging_config
import libs.services.observability as observability


runner = CliRunner(mix_stderr=False)


def _reset_observability() -> None:
    observability._CONFIGURED = False
    observability._CONFIGURED_STREAM_ID = None
    observability._CONFIGURED_LEVEL_NAME = None
    observability._CONFIGURED_FORMAT = None
    observability._CONFIGURED_CONFIG = None
    structlog.reset_defaults()


def _make_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: observability-demo
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
    return project


def test_packaged_logging_config_sets_required_defaults() -> None:
    config = load_logging_config(apply_env=False)

    assert config.logger == "xcron"
    assert config.destination == "stderr"
    assert config.format == "auto"
    assert config.level == "INFO"
    assert config.timestamp == "iso"
    assert config.events.actions is True
    assert config.events.subprocesses is True
    assert config.events.scheduler_wrappers is True
    assert "event" in config.fields.include
    assert "token" in config.fields.redact


def test_logging_env_overrides_default_config(monkeypatch) -> None:
    monkeypatch.setenv("XCRON_LOG_LEVEL", "debug")
    monkeypatch.setenv("XCRON_LOG_FORMAT", "json")

    config = load_logging_config()

    assert config.level == "DEBUG"
    assert config.format == "json"


def test_subprocess_command_logging_redacts_configured_patterns_without_redacting_paths() -> None:
    command = ["/tmp/.venv/bin/tool", "--token", "abc123", "--secret=value", "env=prod", "plain"]

    assert observability.redact_sequence(command, ("token", "secret", "env")) == [
        "/tmp/.venv/bin/tool",
        "--token",
        "[REDACTED]",
        "--secret=[REDACTED]",
        "env=[REDACTED]",
        "plain",
    ]


def test_configured_logger_writes_json_to_stderr(capsys, monkeypatch) -> None:
    monkeypatch.setenv("XCRON_LOG_FORMAT", "json")
    _reset_observability()

    observability.get_logger("xcron.test").info("contract_check")
    captured = capsys.readouterr()

    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["event"] == "contract_check"
    assert payload["level"] == "info"


def test_cli_json_stdout_remains_parseable_while_logs_use_stderr(tmp_path, monkeypatch) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("XCRON_LOG_FORMAT", "json")
    _reset_observability()

    result = runner.invoke(app, ["validate", "--project", str(project), "--output", "json"])

    assert result.exit_code == 0
    stdout_payload = json.loads(result.stdout)
    stderr_events = [json.loads(line)["event"] for line in result.stderr.splitlines()]
    assert stdout_payload["project"] == str(project)
    assert stdout_payload["valid"] is True
    assert "action_started" in stderr_events
    assert "action_finished" in stderr_events

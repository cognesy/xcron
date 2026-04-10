from __future__ import annotations

import json
from pathlib import Path

from libs.services.hook_installer import (
    CODEX_CONFIG_RELATIVE_PATH,
    CODEX_HOOKS_RELATIVE_PATH,
    CLAUDE_SETTINGS_RELATIVE_PATH,
    capture_session_end,
    ensure_agent_hooks,
    inspect_agent_hooks,
)


def test_ensure_agent_hooks_creates_repo_local_configs_and_repairs_paths(tmp_path) -> None:
    first_executable = tmp_path / "bin" / "xcron-a"
    first_executable.parent.mkdir(parents=True)
    first_executable.write_text("", encoding="utf-8")

    result = ensure_agent_hooks(tmp_path, executable_path=first_executable)

    codex_config = tmp_path / CODEX_CONFIG_RELATIVE_PATH
    codex_hooks = tmp_path / CODEX_HOOKS_RELATIVE_PATH
    claude_settings = tmp_path / CLAUDE_SETTINGS_RELATIVE_PATH

    assert codex_config.exists()
    assert codex_hooks.exists()
    assert claude_settings.exists()
    assert "codex_hooks = true" in codex_config.read_text(encoding="utf-8")

    codex_payload = json.loads(codex_hooks.read_text(encoding="utf-8"))
    assert codex_payload["hooks"]["SessionStart"][0]["command"] == f"{first_executable.resolve()} hooks session-start"
    assert codex_payload["hooks"]["SessionEnd"][0]["command"] == f"{first_executable.resolve()} hooks session-end"

    claude_payload = json.loads(claude_settings.read_text(encoding="utf-8"))
    assert claude_payload["hooks"]["SessionStart"][0]["hooks"][0]["command"] == f"{first_executable.resolve()} hooks session-start"
    assert claude_payload["hooks"]["Stop"][0]["hooks"][0]["command"] == f"{first_executable.resolve()} hooks session-end"
    assert result.changed_files

    second_executable = tmp_path / "bin" / "xcron-b"
    second_executable.write_text("", encoding="utf-8")
    repaired = ensure_agent_hooks(tmp_path, executable_path=second_executable)

    repaired_codex_payload = json.loads(codex_hooks.read_text(encoding="utf-8"))
    repaired_claude_payload = json.loads(claude_settings.read_text(encoding="utf-8"))
    assert repaired_codex_payload["hooks"]["SessionStart"][0]["command"] == f"{second_executable.resolve()} hooks session-start"
    assert repaired_claude_payload["hooks"]["SessionStart"][0]["hooks"][0]["command"] == f"{second_executable.resolve()} hooks session-start"
    assert len(repaired_codex_payload["hooks"]["SessionStart"]) == 1
    assert len(repaired_claude_payload["hooks"]["SessionStart"]) == 1
    assert repaired.changed_files


def test_capture_session_end_appends_jsonl_record(tmp_path) -> None:
    log_path = capture_session_end(tmp_path)

    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["cwd"] == str(Path(tmp_path).resolve())
    assert "timestamp" in payload


def test_inspect_agent_hooks_reports_repo_local_status_and_path_health(tmp_path) -> None:
    executable = tmp_path / "bin" / "xcron"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")

    ensure_agent_hooks(tmp_path, executable_path=executable)
    status = inspect_agent_hooks(tmp_path, executable_path=executable)

    assert status.codex.config_exists is True
    assert status.codex.hooks_exists is True
    assert status.codex.feature_enabled is True
    assert status.codex.session_start_matches is True
    assert status.codex.session_end_matches is True
    assert status.claude.settings_exists is True
    assert status.claude.session_start_matches is True
    assert status.claude.stop_matches is True

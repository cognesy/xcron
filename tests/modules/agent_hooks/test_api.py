from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from xcron.capabilities.agent_hooks.api import (
    install_agent_hooks,
    record_session_end,
    resolve_xcron_executable,
    status_agent_hooks,
)
from xcron.capabilities.agent_hooks.contracts import (
    ExecutableNotFoundError,
    HookInstallResult,
    HookStatusResult,
    SessionEndResult,
)


def test_agent_hooks_api_returns_module_owned_immutable_contracts(tmp_path) -> None:
    executable = tmp_path / "xcron"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    installed = install_agent_hooks(tmp_path, executable_path=executable)
    status = status_agent_hooks(tmp_path, executable_path=executable)
    session_end = record_session_end(tmp_path)

    assert isinstance(installed, HookInstallResult)
    assert isinstance(status, HookStatusResult)
    assert isinstance(session_end, SessionEndResult)
    assert status.codex.session_start_matches
    assert status.claude.stop_matches
    assert session_end.log_path.endswith("session-history.jsonl")
    with pytest.raises(FrozenInstanceError):
        installed.executable_path = "changed"  # type: ignore[misc]


def test_resolve_xcron_executable_raises_typed_error(monkeypatch) -> None:
    from xcron.capabilities.agent_hooks import api

    monkeypatch.setattr(api.shutil, "which", lambda _name: None)
    with pytest.raises(ExecutableNotFoundError):
        resolve_xcron_executable()


def test_agent_hooks_owns_exactly_declared_state_paths(tmp_path) -> None:
    unrelated = tmp_path / "README.md"
    unrelated.write_text("keep me\n", encoding="utf-8")

    install_agent_hooks(tmp_path, executable_path="/opt/xcron/bin/xcron")
    record_session_end(tmp_path)

    files = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert files == {
        ".claude/settings.json",
        ".codex/config.toml",
        ".codex/hooks.json",
        "README.md",
        "session-history.jsonl",
    }
    assert unrelated.read_text(encoding="utf-8") == "keep me\n"

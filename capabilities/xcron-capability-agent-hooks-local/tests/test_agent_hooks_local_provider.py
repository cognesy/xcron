"""Behaviour tests for the self-contained agent-hooks provider."""

from __future__ import annotations

import json
from pathlib import Path

from xcron.capabilities.agent_hooks_local.provider import CAPABILITY
from xcron.contracts import AgentHooksPort, HookRequest, InvocationContext, ProjectRequest, Settings, XcronOptions
from xcron.kernel import CapabilityHost, CapabilityRegistry


def _context(root: Path) -> InvocationContext:
    return InvocationContext(XcronOptions.create(root), None, Settings())


def test_agent_hook_files_are_idempotent_and_preserve_unrelated_payload(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir()
    settings_path.write_text('{"unrelated": true}\n', encoding="utf-8")
    host = CapabilityHost(CapabilityRegistry((CAPABILITY,)))
    provider = host.require("agent-hooks", AgentHooksPort)
    request = HookRequest(project_path=tmp_path, executable_path=Path("/bin/echo"))

    installed = provider.install(request, _context(tmp_path))
    second = provider.repair(request, _context(tmp_path))
    status = provider.status(request, _context(tmp_path))
    event = provider.record_session_end(ProjectRequest(project_path=tmp_path), _context(tmp_path))

    claude_payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert installed.changed_files
    assert second.changed_files == ()
    assert status.codex.session_start_matches is True
    assert status.claude.stop_matches is True
    assert claude_payload["unrelated"] is True
    assert Path(event.log_path).read_text(encoding="utf-8").count("\n") == 1
    assert host.freeze().ids() == ("agent-hooks:local",)

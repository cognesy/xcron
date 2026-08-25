"""Safety and behaviour tests for the independently installable log provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from xcron.capabilities.logs_local.provider import CAPABILITY as LOGS
from xcron.capabilities.manifest_yaml.provider import CAPABILITY as MANIFEST
from xcron.capabilities.scheduler_native.provider import CAPABILITY as SCHEDULER
from xcron.capabilities.workspace_local.provider import CAPABILITY as WORKSPACE
from xcron.contracts import InvocationContext, LogPort, LogsRequest, ProjectWorkspace, Settings, XcronOptions
from xcron.kernel import CapabilityHost, CapabilityRegistry


MANIFEST_TEXT = """\
version: 1
project:
  id: logs-provider
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: archive
    command: echo archive
    schedule:
      cron: "0 * * * *"
"""


def _context(tmp_path: Path) -> InvocationContext:
    schedules = tmp_path / "resources" / "schedules"
    schedules.mkdir(parents=True)
    (schedules / "default.yaml").write_text(MANIFEST_TEXT, encoding="utf-8")
    workspace = ProjectWorkspace(tmp_path, schedules, tmp_path / "config.yaml", tmp_path / "marker.toml", None)
    state_root = tmp_path / "state"
    return InvocationContext(
        XcronOptions.create(tmp_path, backend="cron", state_root=state_root),
        workspace,
        Settings(state_root=state_root),
    )


def test_logs_are_dry_run_by_default_and_cannot_clear_outside_owned_log_root(tmp_path: Path) -> None:
    context = _context(tmp_path)
    logs_dir = tmp_path / "state" / "projects" / "logs-provider" / "logs"
    logs_dir.mkdir(parents=True)
    owned = logs_dir / "logs-provider.archive.out.log"
    owned.write_text("owned\n", encoding="utf-8")
    outside = tmp_path / "outside.log"
    outside.write_text("valuable\n", encoding="utf-8")
    escaped = logs_dir / "escape.log"
    try:
        escaped.symlink_to(outside)
    except OSError:
        pytest.skip("the filesystem does not support symlinks")

    host = CapabilityHost(CapabilityRegistry((WORKSPACE, MANIFEST, SCHEDULER, LOGS)))
    provider = host.require("logs", LogPort)
    listed = provider.list(LogsRequest(), context)
    dry_run = provider.clear(LogsRequest(), context)

    assert listed.valid is True
    assert [entry.path for entry in listed.files] == [str(owned)]
    assert dry_run.cleared == 0
    assert owned.read_text(encoding="utf-8") == "owned\n"
    cleared = provider.clear(LogsRequest(dry_run=False), context)
    assert cleared.cleared == 1
    assert owned.read_text(encoding="utf-8") == ""
    assert outside.read_text(encoding="utf-8") == "valuable\n"
    assert host.freeze().ids() == ("manifest:yaml", "workspace:local", "scheduler:native", "logs:local")

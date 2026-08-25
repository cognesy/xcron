"""Marker failure-mode drills owned by the local workspace provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from xcron.capabilities.workspace_local.marker import marker_path
from xcron.capabilities.workspace_local.resolver import resolve_workspace
from xcron.contracts import MalformedMarkerError


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    (root / "schedules").mkdir(parents=True)
    return root


def test_an_unmarked_workspace_warns_and_proceeds(workspace: Path) -> None:
    """Layout-only workspaces remain an advisory-compatible migration path."""
    warned: list[Path] = []

    resolved = resolve_workspace(workspace, on_missing_marker=warned.append)

    assert warned == [workspace.resolve()]
    assert resolved.root == workspace.resolve()
    assert resolved.marker is None
    assert resolved.is_marked is False


def test_an_untrustworthy_marker_stops_resolution_outright(workspace: Path) -> None:
    """A claimed but unreadable identity is unsafe to act on."""
    marker_path(workspace).write_text("not toml at all = = =", encoding="utf-8")

    with pytest.raises(MalformedMarkerError):
        resolve_workspace(workspace)

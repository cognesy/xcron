"""Typed workspace-initialization API."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from xcron.contracts import WorkspaceInitResult, WorkspacePort


class HomeAPI:
    """Initialize an xcron workspace without a CLI dependency."""

    def __init__(self, workspace: WorkspacePort, guard: Callable[[], None], *, created_by: str = "xcron") -> None:
        self._workspace = workspace
        self._guard = guard
        self._created_by = created_by

    def initialize(self, *, xcron_home: str | Path | None = None) -> WorkspaceInitResult:
        self._guard()
        root = None if xcron_home is None else Path(xcron_home).expanduser().resolve()
        return self._workspace.initialize(root, created_by=self._created_by)

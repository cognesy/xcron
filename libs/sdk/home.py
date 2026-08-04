"""Typed workspace-initialization API."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from xcron_libs.capabilities.workspace.api import initialize_workspace
from xcron_libs.capabilities.workspace.contracts import WorkspaceInitResult


class HomeAPI:
    """Initialize an xcron workspace without a CLI dependency."""

    def __init__(self, guard: Callable[[], None], *, created_by: str = "xcron") -> None:
        self._guard = guard
        self._created_by = created_by

    def initialize(self, *, xcron_home: str | Path | None = None) -> WorkspaceInitResult:
        self._guard()
        return initialize_workspace(
            Path(xcron_home).expanduser().resolve() if xcron_home is not None else None,
            created_by=self._created_by,
        )

"""Typed agent-hook API for the selected project root."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from xcron_libs.capabilities.agent_hooks import (
    HookInstallResult,
    HookStatusResult,
    install_agent_hooks,
    record_session_end,
    repair_agent_hooks,
    status_agent_hooks,
)
from xcron_libs.sdk.options import XcronOptions


class HooksAPI:
    """Install, inspect, repair, and invoke existing agent-hook helpers."""

    def __init__(self, options: XcronOptions, guard: Callable[[], None]) -> None:
        self._options = options
        self._guard = guard

    def install(
        self, *, executable_path: str | Path | None = None
    ) -> HookInstallResult:
        self._guard()
        return install_agent_hooks(self._project_root(), executable_path=executable_path)

    def status(
        self, *, executable_path: str | Path | None = None
    ) -> HookStatusResult:
        self._guard()
        return status_agent_hooks(self._project_root(), executable_path=executable_path)

    def repair(
        self, *, executable_path: str | Path | None = None
    ) -> HookInstallResult:
        self._guard()
        return repair_agent_hooks(
            self._project_root(), executable_path=executable_path
        )

    def session_end(self) -> Path:
        self._guard()
        return record_session_end(self._project_root())

    def _project_root(self) -> Path:
        return self._options.project_path or Path.cwd().resolve()

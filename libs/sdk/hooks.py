"""Typed agent-hook API for the selected project root."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

from xcron_libs.capabilities.agent_hooks.api import (
    install_agent_hooks,
    record_session_end,
    repair_agent_hooks,
    resolve_xcron_executable,
    status_agent_hooks,
)
from xcron_libs.capabilities.agent_hooks.contracts import AgentHooksError, HookInstallResult, HookStatusResult
from xcron_libs.sdk.errors import HookError
from xcron_libs.sdk.options import XcronOptions


ResultT = TypeVar("ResultT")


class HooksAPI:
    """Install, inspect, repair, and invoke existing agent-hook helpers."""

    def __init__(self, options: XcronOptions, guard: Callable[[], None]) -> None:
        self._options = options
        self._guard = guard

    def install(
        self, *, executable_path: str | Path | None = None
    ) -> HookInstallResult:
        return self._call(
            lambda: install_agent_hooks(self._project_root(), executable_path=executable_path)
        )

    def status(
        self, *, executable_path: str | Path | None = None
    ) -> HookStatusResult:
        return self._call(
            lambda: status_agent_hooks(self._project_root(), executable_path=executable_path)
        )

    def repair(
        self, *, executable_path: str | Path | None = None
    ) -> HookInstallResult:
        return self._call(
            lambda: repair_agent_hooks(
                self._project_root(), executable_path=executable_path
            )
        )

    def session_end(self) -> Path:
        result = self._call(lambda: record_session_end(self._project_root()))
        return Path(result.log_path)

    def resolve_executable(self) -> str:
        """Resolve the executable used by installed hook commands."""

        return self._call(resolve_xcron_executable)

    def _call(self, operation: Callable[[], ResultT]) -> ResultT:
        self._guard()
        try:
            return operation()
        except AgentHooksError as exc:
            raise HookError(str(exc)) from exc

    def _project_root(self) -> Path:
        return self._options.project_path or Path.cwd().resolve()

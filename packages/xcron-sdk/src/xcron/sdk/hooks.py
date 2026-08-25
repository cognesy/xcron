"""Typed agent-hook API for the selected project root."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from xcron.contracts import (
    AgentHooksError,
    AgentHooksPort,
    HookInstallResult,
    HookRequest,
    HookStatusResult,
    InvocationContext,
    ProjectRequest,
)
from xcron.sdk.errors import HookError


ResultT = TypeVar("ResultT")


class HooksAPI:
    """Install, inspect, repair, and invoke existing agent-hook helpers."""

    def __init__(
        self,
        hooks: AgentHooksPort,
        context: InvocationContext,
        guard: Callable[[], None],
    ) -> None:
        self._hooks = hooks
        self._context = context
        self._guard = guard

    def install(self, *, executable_path: str | Path | None = None) -> HookInstallResult:
        return self._call(lambda: self._hooks.install(_request(self._context, executable_path), self._context))

    def status(self, *, executable_path: str | Path | None = None) -> HookStatusResult:
        return self._call(lambda: self._hooks.status(_request(self._context, executable_path), self._context))

    def repair(self, *, executable_path: str | Path | None = None) -> HookInstallResult:
        return self._call(lambda: self._hooks.repair(_request(self._context, executable_path), self._context))

    def session_end(self) -> Path:
        result = self._call(lambda: self._hooks.record_session_end(_project(self._context), self._context))
        return Path(result.log_path)

    def resolve_executable(self) -> str:
        """Resolve the executable that installed hooks would invoke."""
        return self._call(lambda: self._hooks.status(_request(self._context, None), self._context).executable_path)

    def _call(self, operation: Callable[[], ResultT]) -> ResultT:
        self._guard()
        try:
            return operation()
        except AgentHooksError as error:
            raise HookError(str(error)) from error


def _project(context: InvocationContext) -> ProjectRequest:
    return ProjectRequest(
        project_path=context.options.project_path,
        schedule_name=context.options.schedule_name,
    )


def _request(context: InvocationContext, executable_path: str | Path | None) -> HookRequest:
    return HookRequest(
        **_project(context).model_dump(),
        executable_path=None if executable_path is None else Path(executable_path).expanduser().resolve(),
    )

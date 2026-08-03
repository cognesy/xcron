"""Stable data contracts for the agent-hooks capability."""

from __future__ import annotations

from dataclasses import dataclass


class AgentHooksError(RuntimeError):
    """Base error raised by the agent-hooks capability."""


class ExecutableNotFoundError(AgentHooksError):
    """Raised when the xcron executable cannot be resolved for a hook."""


@dataclass(frozen=True)
class CodexHookStatus:
    config_path: str
    hooks_path: str
    config_exists: bool
    hooks_exists: bool
    feature_enabled: bool
    session_start_matches: bool
    session_end_matches: bool


@dataclass(frozen=True)
class ClaudeHookStatus:
    settings_path: str
    settings_exists: bool
    session_start_matches: bool
    stop_matches: bool


@dataclass(frozen=True)
class HookInstallResult:
    executable_path: str
    codex_config_path: str
    codex_hooks_path: str
    claude_settings_path: str
    changed_files: tuple[str, ...]


@dataclass(frozen=True)
class HookStatusResult:
    executable_path: str
    codex: CodexHookStatus
    claude: ClaudeHookStatus


@dataclass(frozen=True)
class SessionEndResult:
    log_path: str


__all__ = [
    "AgentHooksError",
    "ClaudeHookStatus",
    "CodexHookStatus",
    "ExecutableNotFoundError",
    "HookInstallResult",
    "HookStatusResult",
    "SessionEndResult",
]

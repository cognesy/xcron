"""Public API for the agent-hooks capability.

The implementation is intentionally private to this package. Callers receive
only the contracts from :mod:`contracts`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from ._claude import ensure_claude_hooks, inspect_claude_hooks
from ._codex import ensure_codex_hooks, inspect_codex_hooks
from ._paths import (
    CLAUDE_SETTINGS_RELATIVE_PATH,
    CODEX_CONFIG_RELATIVE_PATH,
    CODEX_HOOKS_RELATIVE_PATH,
    SESSION_LOG_RELATIVE_PATH,
)

from .contracts import (
    AgentHooksError,
    ClaudeHookStatus,
    CodexHookStatus,
    ExecutableNotFoundError,
    HookInstallResult,
    HookStatusResult,
    SessionEndResult,
)


def resolve_xcron_executable() -> str:
    """Return the resolved xcron executable path."""

    try:
        executable = shutil.which("xcron")
    except OSError as exc:
        raise AgentHooksError(str(exc)) from exc
    if executable:
        return str(Path(executable).expanduser().resolve())
    raise ExecutableNotFoundError("unable to resolve xcron executable for hook installation")


def install_agent_hooks(
    project_root: str | Path, *, executable_path: str | Path | None = None
) -> HookInstallResult:
    """Install or update the repo-local agent hooks."""

    root = Path(project_root).expanduser().resolve()
    executable = _resolve_executable(executable_path)
    changed_files: list[str] = []

    codex_changed, codex_status = ensure_codex_hooks(root, executable)
    if codex_changed:
        changed_files.extend([codex_status.config_path, codex_status.hooks_path])

    claude_changed, claude_status = ensure_claude_hooks(root, executable)
    if claude_changed:
        changed_files.append(claude_status.settings_path)

    return HookInstallResult(
        executable_path=str(executable),
        codex_config_path=str(root / CODEX_CONFIG_RELATIVE_PATH),
        codex_hooks_path=str(root / CODEX_HOOKS_RELATIVE_PATH),
        claude_settings_path=str(root / CLAUDE_SETTINGS_RELATIVE_PATH),
        changed_files=tuple(dict.fromkeys(changed_files)),
    )


def status_agent_hooks(
    project_root: str | Path, *, executable_path: str | Path | None = None
) -> HookStatusResult:
    """Inspect the repo-local agent hook state."""

    root = Path(project_root).expanduser().resolve()
    executable = _resolve_executable(executable_path)
    codex = inspect_codex_hooks(root, executable)
    claude = inspect_claude_hooks(root, executable)
    return HookStatusResult(
        executable_path=str(executable),
        codex=CodexHookStatus(**vars(codex)),
        claude=ClaudeHookStatus(**vars(claude)),
    )


def repair_agent_hooks(
    project_root: str | Path, *, executable_path: str | Path | None = None
) -> HookInstallResult:
    """Repair the repo-local agent hooks."""

    return install_agent_hooks(project_root, executable_path=executable_path)


def record_session_end(project_root: str | Path) -> SessionEndResult:
    """Record a minimal session-end event and return its log location."""

    root = Path(project_root).expanduser().resolve()
    log_path = root / SESSION_LOG_RELATIVE_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "cwd": str(root)}
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True))
        handle.write("\n")
    return SessionEndResult(log_path=str(log_path))


def _resolve_executable(executable_path: str | Path | None) -> Path:
    if executable_path is not None:
        return Path(executable_path).expanduser().resolve()
    return Path(resolve_xcron_executable())


__all__ = [
    "install_agent_hooks",
    "record_session_end",
    "repair_agent_hooks",
    "resolve_xcron_executable",
    "status_agent_hooks",
]

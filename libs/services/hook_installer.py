"""Agent hook installation helpers for Codex and Claude Code."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from libs.services.claude_hooks import ClaudeHookStatus, ensure_claude_hooks, inspect_claude_hooks
from libs.services.codex_hooks import CodexHookStatus, ensure_codex_hooks, inspect_codex_hooks
from libs.services.hook_paths import (
    CLAUDE_SETTINGS_RELATIVE_PATH,
    CODEX_CONFIG_RELATIVE_PATH,
    CODEX_HOOKS_RELATIVE_PATH,
    SESSION_LOG_RELATIVE_PATH,
)


@dataclass(frozen=True)
class HookInstallResult:
    """Structured result for hook installation/update."""

    executable_path: str
    codex_config_path: str
    codex_hooks_path: str
    claude_settings_path: str
    changed_files: tuple[str, ...]


@dataclass(frozen=True)
class HookStatusResult:
    """Structured status for repo-local hook integrations."""

    executable_path: str
    codex: CodexHookStatus
    claude: ClaudeHookStatus


def resolve_xcron_executable() -> Path:
    """Resolve the current xcron executable path for hook commands."""

    executable = shutil.which("xcron")
    if executable:
        return Path(executable).expanduser().resolve()
    raise RuntimeError("unable to resolve xcron executable for hook installation")


def ensure_agent_hooks(project_root: str | Path, *, executable_path: str | Path | None = None) -> HookInstallResult:
    """Ensure repo-local Codex and Claude hook files exist and are current."""

    root = Path(project_root).expanduser().resolve()
    executable = Path(executable_path).expanduser().resolve() if executable_path is not None else resolve_xcron_executable()

    changed_files: list[str] = []

    codex_changed, codex_status = ensure_codex_hooks(root, executable)
    if codex_changed:
        changed_files.append(codex_status.config_path)
        changed_files.append(codex_status.hooks_path)

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


def inspect_agent_hooks(project_root: str | Path, *, executable_path: str | Path | None = None) -> HookStatusResult:
    """Inspect current repo-local hook state for all supported targets."""

    root = Path(project_root).expanduser().resolve()
    executable = Path(executable_path).expanduser().resolve() if executable_path is not None else resolve_xcron_executable()
    return HookStatusResult(
        executable_path=str(executable),
        codex=inspect_codex_hooks(root, executable),
        claude=inspect_claude_hooks(root, executable),
    )


def capture_session_end(project_root: str | Path) -> Path:
    """Append a minimal session-end record for future context enrichment."""

    root = Path(project_root).expanduser().resolve()
    log_path = root / SESSION_LOG_RELATIVE_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cwd": str(root),
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True))
        handle.write("\n")
    return log_path


__all__ = [
    "CLAUDE_SETTINGS_RELATIVE_PATH",
    "CODEX_CONFIG_RELATIVE_PATH",
    "CODEX_HOOKS_RELATIVE_PATH",
    "HookInstallResult",
    "HookStatusResult",
    "capture_session_end",
    "ensure_agent_hooks",
    "inspect_agent_hooks",
    "resolve_xcron_executable",
]

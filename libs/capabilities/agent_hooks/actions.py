"""Use-case boundary around repository-local agent hook services."""

from __future__ import annotations

from pathlib import Path

from xcron_libs.services.hook_installer import (
    HookInstallResult,
    HookStatusResult,
    capture_session_end,
    ensure_agent_hooks,
    inspect_agent_hooks,
)


def install_agent_hooks(
    project_root: str | Path,
    *,
    executable_path: str | Path | None = None,
) -> HookInstallResult:
    """Install the declared Codex and Claude hooks for one repository."""
    return ensure_agent_hooks(project_root, executable_path=executable_path)


def status_agent_hooks(
    project_root: str | Path,
    *,
    executable_path: str | Path | None = None,
) -> HookStatusResult:
    """Inspect hook state without projecting it for a specific channel."""
    return inspect_agent_hooks(project_root, executable_path=executable_path)


def repair_agent_hooks(
    project_root: str | Path,
    *,
    executable_path: str | Path | None = None,
) -> HookInstallResult:
    """Repair is intentionally the idempotent install operation."""
    return install_agent_hooks(project_root, executable_path=executable_path)


def record_session_end(project_root: str | Path) -> Path:
    """Record the existing session-end evidence for one repository."""
    return capture_session_end(project_root)

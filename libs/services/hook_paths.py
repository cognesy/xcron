"""Shared repo-local hook path constants."""

from __future__ import annotations

from pathlib import Path


CODEX_HOOKS_RELATIVE_PATH = Path(".codex/hooks.json")
CODEX_CONFIG_RELATIVE_PATH = Path(".codex/config.toml")
CLAUDE_SETTINGS_RELATIVE_PATH = Path(".claude/settings.json")
SESSION_LOG_RELATIVE_PATH = Path(".xcron/session-history.jsonl")


__all__ = [
    "CLAUDE_SETTINGS_RELATIVE_PATH",
    "CODEX_CONFIG_RELATIVE_PATH",
    "CODEX_HOOKS_RELATIVE_PATH",
    "SESSION_LOG_RELATIVE_PATH",
]

"""Private state-path declarations owned by the agent-hooks module."""

from pathlib import Path

CLAUDE_SETTINGS_RELATIVE_PATH = Path(".claude/settings.json")
CODEX_CONFIG_RELATIVE_PATH = Path(".codex/config.toml")
CODEX_HOOKS_RELATIVE_PATH = Path(".codex/hooks.json")
SESSION_LOG_RELATIVE_PATH = Path("session-history.jsonl")

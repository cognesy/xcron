"""Repo-local Claude hook/config integration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from libs.services.hook_paths import CLAUDE_SETTINGS_RELATIVE_PATH


@dataclass(frozen=True)
class ClaudeHookStatus:
    settings_path: str
    settings_exists: bool
    session_start_matches: bool
    stop_matches: bool


def ensure_claude_hooks(project_root: Path, executable: Path) -> tuple[bool, ClaudeHookStatus]:
    settings_path = project_root / CLAUDE_SETTINGS_RELATIVE_PATH
    changed = _ensure_claude_settings(settings_path, executable)
    return changed, inspect_claude_hooks(project_root, executable)


def inspect_claude_hooks(project_root: Path, executable: Path) -> ClaudeHookStatus:
    settings_path = project_root / CLAUDE_SETTINGS_RELATIVE_PATH
    payload = _load_json_file(settings_path) if settings_path.exists() else {}
    hooks = payload.get("hooks", {}) if isinstance(payload, dict) else {}
    return ClaudeHookStatus(
        settings_path=str(settings_path),
        settings_exists=settings_path.exists(),
        session_start_matches=_claude_hook_matches(hooks, "SessionStart", _session_start_command(executable)),
        stop_matches=_claude_hook_matches(hooks, "Stop", _session_end_command(executable)),
    )


def _ensure_claude_settings(settings_path: Path, executable: Path) -> bool:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_json_file(settings_path)
    hooks = payload.setdefault("hooks", {})
    changed = False
    changed |= _upsert_claude_hook(hooks, "SessionStart", _session_start_command(executable))
    changed |= _upsert_claude_hook(hooks, "Stop", _session_end_command(executable))
    if changed or not settings_path.exists():
        settings_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return changed or not settings_path.exists()


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def _session_start_command(executable: Path) -> str:
    return f"{executable} hooks session-start"


def _session_end_command(executable: Path) -> str:
    return f"{executable} hooks session-end"


def _upsert_claude_hook(hooks: dict[str, Any], event_name: str, command: str) -> bool:
    entries = hooks.get(event_name)
    if not isinstance(entries, list):
        hooks[event_name] = [{"hooks": [{"type": "command", "command": command}]}]
        return True

    suffix = command.split(" ", 1)[1]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hook_items = entry.get("hooks")
        if not isinstance(hook_items, list):
            continue
        for hook in hook_items:
            if not isinstance(hook, dict):
                continue
            existing = hook.get("command")
            if isinstance(existing, str) and existing.endswith(suffix):
                if existing != command or hook.get("type") != "command":
                    hook["type"] = "command"
                    hook["command"] = command
                    return True
                return False

    entries.append({"hooks": [{"type": "command", "command": command}]})
    return True


def _claude_hook_matches(hooks: dict[str, Any], event_name: str, command: str) -> bool:
    entries = hooks.get(event_name)
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hook_items = entry.get("hooks")
        if not isinstance(hook_items, list):
            continue
        for hook in hook_items:
            if isinstance(hook, dict) and hook.get("command") == command:
                return True
    return False


__all__ = ["ClaudeHookStatus", "ensure_claude_hooks", "inspect_claude_hooks"]

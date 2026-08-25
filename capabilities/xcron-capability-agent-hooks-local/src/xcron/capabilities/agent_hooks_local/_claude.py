"""Private Claude hook-file adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xcron.capabilities.agent_hooks_local._paths import CLAUDE_SETTINGS_RELATIVE_PATH
from xcron.contracts import ClaudeHookStatus


def ensure_claude_hooks(project_root: Path, executable: Path) -> tuple[bool, ClaudeHookStatus]:
    path = project_root / CLAUDE_SETTINGS_RELATIVE_PATH
    changed = _ensure_settings(path, executable)
    return changed, inspect_claude_hooks(project_root, executable)


def inspect_claude_hooks(project_root: Path, executable: Path) -> ClaudeHookStatus:
    path = project_root / CLAUDE_SETTINGS_RELATIVE_PATH
    payload = _load_json_file(path) if path.exists() else {}
    hooks = payload.get("hooks", {}) if isinstance(payload, dict) else {}
    return ClaudeHookStatus(
        settings_path=str(path),
        settings_exists=path.exists(),
        session_start_matches=_matches(hooks, "SessionStart", _start(executable)),
        stop_matches=_matches(hooks, "Stop", _end(executable)),
    )


def _ensure_settings(path: Path, executable: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_json_file(path)
    hooks = payload.setdefault("hooks", {})
    changed = _upsert(hooks, "SessionStart", _start(executable))
    changed |= _upsert(hooks, "Stop", _end(executable))
    if changed or not path.exists():
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return changed or not path.exists()


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _start(executable: Path) -> str:
    return f"{executable} hooks session-start"


def _end(executable: Path) -> str:
    return f"{executable} hooks session-end"


def _upsert(hooks: dict[str, Any], event_name: str, command: str) -> bool:
    entries = hooks.get(event_name)
    if not isinstance(entries, list):
        hooks[event_name] = [{"hooks": [{"type": "command", "command": command}]}]
        return True
    suffix = command.split(" ", 1)[1]
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
            continue
        for hook in entry["hooks"]:
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


def _matches(hooks: object, event_name: str, command: str) -> bool:
    if not isinstance(hooks, dict) or not isinstance(hooks.get(event_name), list):
        return False
    return any(
        isinstance(hook, dict) and hook.get("command") == command
        for entry in hooks[event_name]
        if isinstance(entry, dict) and isinstance(entry.get("hooks"), list)
        for hook in entry["hooks"]
    )

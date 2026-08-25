"""Private Codex hook-file adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xcron.capabilities.agent_hooks_local._paths import CODEX_CONFIG_RELATIVE_PATH, CODEX_HOOKS_RELATIVE_PATH
from xcron.contracts import CodexHookStatus


def ensure_codex_hooks(project_root: Path, executable: Path) -> tuple[bool, CodexHookStatus]:
    config_path = project_root / CODEX_CONFIG_RELATIVE_PATH
    hooks_path = project_root / CODEX_HOOKS_RELATIVE_PATH
    changed = _ensure_codex_config(config_path)
    changed |= _ensure_codex_hooks_file(hooks_path, executable)
    return changed, inspect_codex_hooks(project_root, executable)


def inspect_codex_hooks(project_root: Path, executable: Path) -> CodexHookStatus:
    config_path = project_root / CODEX_CONFIG_RELATIVE_PATH
    hooks_path = project_root / CODEX_HOOKS_RELATIVE_PATH
    feature_enabled = config_path.exists() and "codex_hooks = true" in config_path.read_text(encoding="utf-8")
    payload = _load_json_file(hooks_path) if hooks_path.exists() else {}
    hooks = payload.get("hooks", {}) if isinstance(payload, dict) else {}
    return CodexHookStatus(
        config_path=str(config_path),
        hooks_path=str(hooks_path),
        config_exists=config_path.exists(),
        hooks_exists=hooks_path.exists(),
        feature_enabled=feature_enabled,
        session_start_matches=_matches(hooks, "SessionStart", _start(executable)),
        session_end_matches=_matches(hooks, "SessionEnd", _end(executable)),
    )


def _ensure_codex_config(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    feature_index = next((index for index, line in enumerate(lines) if line.strip() == "[features]"), None)
    changed = False
    if feature_index is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(["[features]", "codex_hooks = true"])
        changed = True
    else:
        index = feature_index + 1
        while index < len(lines) and not lines[index].startswith("["):
            if lines[index].strip().startswith("codex_hooks"):
                if lines[index].strip() != "codex_hooks = true":
                    lines[index] = "codex_hooks = true"
                    changed = True
                break
            index += 1
        else:
            lines.insert(index, "codex_hooks = true")
            changed = True
    if changed or not path.exists():
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return changed or not bool(original)


def _ensure_codex_hooks_file(path: Path, executable: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_json_file(path)
    hooks = payload.setdefault("hooks", {})
    changed = _upsert(hooks, "SessionStart", _start(executable))
    changed |= _upsert(hooks, "SessionEnd", _end(executable))
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
        hooks[event_name] = [{"type": "command", "command": command}]
        return True
    suffix = command.split(" ", 1)[1]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        existing = entry.get("command")
        if isinstance(existing, str) and existing.endswith(suffix):
            if existing != command or entry.get("type") != "command":
                entry["type"] = "command"
                entry["command"] = command
                return True
            return False
    entries.append({"type": "command", "command": command})
    return True


def _matches(hooks: object, event_name: str, command: str) -> bool:
    if not isinstance(hooks, dict) or not isinstance(hooks.get(event_name), list):
        return False
    return any(isinstance(entry, dict) and entry.get("command") == command for entry in hooks[event_name])

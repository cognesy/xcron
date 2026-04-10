"""Repo-local Codex hook/config integration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from libs.services.hook_paths import CODEX_CONFIG_RELATIVE_PATH, CODEX_HOOKS_RELATIVE_PATH


@dataclass(frozen=True)
class CodexHookStatus:
    config_path: str
    hooks_path: str
    config_exists: bool
    hooks_exists: bool
    feature_enabled: bool
    session_start_matches: bool
    session_end_matches: bool


def ensure_codex_hooks(project_root: Path, executable: Path) -> tuple[bool, CodexHookStatus]:
    config_path = project_root / CODEX_CONFIG_RELATIVE_PATH
    hooks_path = project_root / CODEX_HOOKS_RELATIVE_PATH

    changed = False
    changed |= _ensure_codex_config(config_path)
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
        session_start_matches=_codex_hook_matches(hooks, "SessionStart", _session_start_command(executable)),
        session_end_matches=_codex_hook_matches(hooks, "SessionEnd", _session_end_command(executable)),
    )


def _ensure_codex_config(config_path: Path) -> bool:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    original = config_path.read_text(encoding="utf-8") if config_path.exists() else ""

    lines = original.splitlines()
    feature_index = next((index for index, line in enumerate(lines) if line.strip() == "[features]"), None)
    changed = False

    if feature_index is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(["[features]", "codex_hooks = true"])
        changed = True
    else:
        insert_index = feature_index + 1
        while insert_index < len(lines) and not lines[insert_index].startswith("["):
            if lines[insert_index].strip().startswith("codex_hooks"):
                if lines[insert_index].strip() != "codex_hooks = true":
                    lines[insert_index] = "codex_hooks = true"
                    changed = True
                break
            insert_index += 1
        else:
            lines.insert(insert_index, "codex_hooks = true")
            changed = True

    if changed or not config_path.exists():
        config_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return changed or not bool(original)


def _ensure_codex_hooks_file(hooks_path: Path, executable: Path) -> bool:
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_json_file(hooks_path)
    hooks = payload.setdefault("hooks", {})
    changed = False
    changed |= _upsert_codex_hook(hooks, "SessionStart", _session_start_command(executable))
    changed |= _upsert_codex_hook(hooks, "SessionEnd", _session_end_command(executable))
    if changed or not hooks_path.exists():
        hooks_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return changed or not hooks_path.exists()


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


def _upsert_codex_hook(hooks: dict[str, Any], event_name: str, command: str) -> bool:
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


def _codex_hook_matches(hooks: dict[str, Any], event_name: str, command: str) -> bool:
    entries = hooks.get(event_name)
    if not isinstance(entries, list):
        return False
    return any(isinstance(entry, dict) and entry.get("command") == command for entry in entries)


__all__ = ["CodexHookStatus", "ensure_codex_hooks", "inspect_codex_hooks"]

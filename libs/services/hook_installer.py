"""Agent hook installation helpers for Codex and Claude Code."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any


CODEX_HOOKS_RELATIVE_PATH = Path(".codex/hooks.json")
CODEX_CONFIG_RELATIVE_PATH = Path(".codex/config.toml")
CLAUDE_SETTINGS_RELATIVE_PATH = Path(".claude/settings.json")
SESSION_LOG_RELATIVE_PATH = Path(".xcron/session-history.jsonl")


@dataclass(frozen=True)
class HookInstallResult:
    """Structured result for hook installation/update."""

    executable_path: str
    codex_config_path: str
    codex_hooks_path: str
    claude_settings_path: str
    changed_files: tuple[str, ...]


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

    codex_config_path = root / CODEX_CONFIG_RELATIVE_PATH
    codex_hooks_path = root / CODEX_HOOKS_RELATIVE_PATH
    claude_settings_path = root / CLAUDE_SETTINGS_RELATIVE_PATH

    if _ensure_codex_config(codex_config_path):
        changed_files.append(str(codex_config_path))
    if _ensure_codex_hooks(codex_hooks_path, executable):
        changed_files.append(str(codex_hooks_path))
    if _ensure_claude_settings(claude_settings_path, executable):
        changed_files.append(str(claude_settings_path))

    return HookInstallResult(
        executable_path=str(executable),
        codex_config_path=str(codex_config_path),
        codex_hooks_path=str(codex_hooks_path),
        claude_settings_path=str(claude_settings_path),
        changed_files=tuple(changed_files),
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


def _ensure_codex_config(config_path: Path) -> bool:
    """Ensure repo-local Codex config enables hooks."""

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


def _ensure_codex_hooks(hooks_path: Path, executable: Path) -> bool:
    """Ensure repo-local Codex hooks point at the current executable."""

    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_json_file(hooks_path)
    hooks = payload.setdefault("hooks", {})

    changed = False
    session_start = _upsert_codex_hook(hooks, "SessionStart", _session_start_command(executable))
    session_end = _upsert_codex_hook(hooks, "SessionEnd", _session_end_command(executable))
    changed = session_start or session_end

    if changed or not hooks_path.exists():
        hooks_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return changed or not hooks_path.exists()


def _ensure_claude_settings(settings_path: Path, executable: Path) -> bool:
    """Ensure repo-local Claude settings include xcron session hooks."""

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
    """Load one JSON object file or return an empty object."""

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
    """Insert or update one Codex hook event entry."""

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


def _upsert_claude_hook(hooks: dict[str, Any], event_name: str, command: str) -> bool:
    """Insert or update one Claude hook event entry."""

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


__all__ = [
    "CODEX_CONFIG_RELATIVE_PATH",
    "CODEX_HOOKS_RELATIVE_PATH",
    "CLAUDE_SETTINGS_RELATIVE_PATH",
    "HookInstallResult",
    "capture_session_end",
    "ensure_agent_hooks",
    "resolve_xcron_executable",
]

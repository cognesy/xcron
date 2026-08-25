"""Installed repo-local agent-hooks provider."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from xcron.capabilities.agent_hooks_local._claude import ensure_claude_hooks, inspect_claude_hooks
from xcron.capabilities.agent_hooks_local._codex import ensure_codex_hooks, inspect_codex_hooks
from xcron.capabilities.agent_hooks_local._paths import (
    CLAUDE_SETTINGS_RELATIVE_PATH,
    CODEX_CONFIG_RELATIVE_PATH,
    CODEX_HOOKS_RELATIVE_PATH,
    SESSION_LOG_RELATIVE_PATH,
)
from xcron.contracts import (
    AgentHooksError,
    AgentHooksPort,
    ExecutableNotFoundError,
    HookInstallResult,
    HookRequest,
    HookStatusResult,
    InvocationContext,
    ProjectRequest,
    SessionEndResult,
)
from xcron.kernel import Capability, CapabilityDescriptor, CapabilityProvides, CapabilityRegistration


class LocalAgentHooksProvider:
    """Own the idempotent Codex/Claude hook-file integration for one project."""

    def install(self, request: HookRequest, context: InvocationContext) -> HookInstallResult:
        root = _root(request, context)
        executable = _executable(request.executable_path)
        changed_files: list[str] = []
        codex_changed, codex_status = ensure_codex_hooks(root, executable)
        if codex_changed:
            changed_files.extend((codex_status.config_path, codex_status.hooks_path))
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

    def status(self, request: HookRequest, context: InvocationContext) -> HookStatusResult:
        root = _root(request, context)
        executable = _executable(request.executable_path)
        codex = inspect_codex_hooks(root, executable)
        claude = inspect_claude_hooks(root, executable)
        return HookStatusResult(
            executable_path=str(executable),
            codex=codex,
            claude=claude,
        )

    def repair(self, request: HookRequest, context: InvocationContext) -> HookInstallResult:
        return self.install(request, context)

    def record_session_end(self, request: ProjectRequest, context: InvocationContext) -> SessionEndResult:
        root = _root(request, context)
        path = root / SESSION_LOG_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "cwd": str(root)}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True))
            handle.write("\n")
        return SessionEndResult(log_path=str(path))


def _root(request: ProjectRequest, context: InvocationContext) -> Path:
    selected = request.project_path
    if selected is None and context.workspace is not None:
        selected = context.workspace.root
    if selected is None:
        selected = context.options.project_path
    if selected is None:
        selected = Path.cwd()
    return Path(selected).expanduser().resolve()


def _executable(value: Path | None) -> Path:
    if value is not None:
        return value.expanduser().resolve()
    try:
        resolved = shutil.which("xcron")
    except OSError as error:
        raise AgentHooksError(str(error)) from error
    if resolved is None:
        raise ExecutableNotFoundError("unable to resolve xcron executable for hook installation")
    return Path(resolved).expanduser().resolve()


DESCRIPTOR = CapabilityDescriptor(
    capability="agent-hooks",
    implementation="local",
    version="0.1.4",
    kernel_api=">=1,<2",
    provides=CapabilityProvides(ports=("agent-hooks",), cli_paths=("hooks",)),
)


def _build(_: object) -> CapabilityRegistration:
    return CapabilityRegistration(ports={"agent-hooks": LocalAgentHooksProvider()}, cli_paths={"hooks": None})


CAPABILITY = Capability(DESCRIPTOR, _build)

assert isinstance(LocalAgentHooksProvider(), AgentHooksPort)

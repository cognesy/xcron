"""Mechanical checks for the scheduler adapter boundary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from xcron_libs.capabilities.reconciliation import SchedulerRegistry, SchedulerRuntimeOptions


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AGENT_HOOKS_ROOT = "xcron_libs.capabilities.agent_hooks"
AGENT_HOOKS_PUBLIC = {
    f"{AGENT_HOOKS_ROOT}.api",
    f"{AGENT_HOOKS_ROOT}.contracts",
}
BACKEND_MODULES = tuple(sorted((REPOSITORY_ROOT / "libs" / "services" / "backends").glob("*_service.py")))
CAPABILITY_MODULES = tuple(sorted((REPOSITORY_ROOT / "libs" / "capabilities").rglob("*.py")))
DOMAIN_MODULES = tuple(sorted((REPOSITORY_ROOT / "libs" / "domain").rglob("*.py")))
RUNTIME_MODULES = tuple(sorted((REPOSITORY_ROOT / "libs" / "runtime").rglob("*.py")))
ACTION_SHIMS = tuple(
    path
    for path in sorted((REPOSITORY_ROOT / "libs" / "actions").glob("*.py"))
    if path.name != "__init__.py"
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def _agent_hooks_import_violations(source: str) -> set[str]:
    """Return agent-hooks imports that bypass its public API/contracts."""

    tree = ast.parse(source)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == AGENT_HOOKS_ROOT or alias.name.startswith(f"{AGENT_HOOKS_ROOT}."):
                    if alias.name not in AGENT_HOOKS_PUBLIC:
                        violations.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            module = node.module
            if module == AGENT_HOOKS_ROOT:
                for alias in node.names:
                    if alias.name not in {"api", "contracts"}:
                        violations.add(f"{module}.{alias.name}")
            elif module.startswith(f"{AGENT_HOOKS_ROOT}."):
                if module not in AGENT_HOOKS_PUBLIC:
                    violations.add(module)
                else:
                    for alias in node.names:
                        if alias.name.startswith("_"):
                            violations.add(f"{module}.{alias.name}")
    return violations


def test_agent_hooks_public_surface_checker_has_planted_negative_examples() -> None:
    forbidden = (
        "import xcron_libs.capabilities.agent_hooks._codex",
        "import xcron_libs.capabilities.agent_hooks._codex as private_hooks",
        "from xcron_libs.capabilities.agent_hooks import _codex",
        "from xcron_libs.capabilities.agent_hooks import _codex as private_hooks",
        "from xcron_libs.capabilities.agent_hooks._codex import CodexHookStatus",
        "from xcron_libs.capabilities.agent_hooks._codex import CodexHookStatus as Status",
    )
    allowed = (
        "import xcron_libs.capabilities.agent_hooks.api as hooks_api",
        "from xcron_libs.capabilities.agent_hooks import api as hooks_api",
        "from xcron_libs.capabilities.agent_hooks.api import install_agent_hooks",
        "from xcron_libs.capabilities.agent_hooks.contracts import HookInstallResult as Result",
    )

    for source in forbidden:
        assert _agent_hooks_import_violations(source), source
    for source in allowed:
        assert _agent_hooks_import_violations(source) == set(), source


def test_agent_hooks_module_has_no_sibling_or_channel_imports() -> None:
    module_root = REPOSITORY_ROOT / "libs" / "capabilities" / "agent_hooks"
    own_modules = {"_claude", "_codex", "_paths", "contracts"}
    forbidden_prefixes = (
        "xcron_cli",
        "xcron_libs.sdk",
        "xcron_libs.services",
        "xcron_libs.capabilities.",
        "typer",
        "rich",
    )

    for path in sorted(module_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                if isinstance(node, ast.Import):
                    assert not any(alias.name.startswith(forbidden_prefixes) for alias in node.names), path
                continue
            if node.level:
                assert node.level == 1, path
                assert node.module in own_modules, (path, node.module)
            elif node.module:
                assert not node.module.startswith(forbidden_prefixes), (path, node.module)


def test_scheduler_adapters_do_not_import_actions_or_sdk() -> None:
    """Adapters receive leaf contracts, never their coordinating action results."""
    for module in BACKEND_MODULES:
        imported = _imported_modules(module)
        assert not any(name.startswith("xcron_libs.actions") for name in imported), module
        assert not any(name.startswith("xcron_libs.sdk") for name in imported), module


def test_typer_shell_uses_the_sdk_not_action_implementations() -> None:
    imported = _imported_modules(REPOSITORY_ROOT / "apps" / "cli" / "typer_app.py")
    forbidden_prefixes = (
        "xcron_libs.actions",
        "xcron_libs.capabilities",
        "xcron_libs.services.backends",
    )

    assert "xcron_libs" in imported
    assert not any(name.startswith(forbidden_prefixes) for name in imported)


def test_capabilities_do_not_depend_on_the_cli_or_rendering_boundary() -> None:
    forbidden_prefixes = (
        "xcron_cli",
        "typer",
        "rich",
        "xcron_libs.services.toon_renderer",
        "xcron_libs.services.tmux_renderer",
        "xcron_libs.services.cli_contracts",
        "xcron_libs.services.cli_mappers",
        "xcron_libs.services.cli_responses",
    )
    for module in CAPABILITY_MODULES:
        imported = _imported_modules(module)
        assert not any(name.startswith(forbidden_prefixes) for name in imported), module
        assert "xcron_libs.services" not in imported, module


def test_domain_does_not_depend_on_channels_or_application_layers() -> None:
    forbidden_prefixes = (
        "xcron_cli",
        "xcron_libs.actions",
        "xcron_libs.capabilities",
        "xcron_libs.runtime",
        "xcron_libs.sdk",
        "xcron_libs.services.backends",
    )
    for module in DOMAIN_MODULES:
        imported = _imported_modules(module)
        assert not any(name.startswith(forbidden_prefixes) for name in imported), module


def test_runtime_is_composition_only_and_channel_independent() -> None:
    forbidden_prefixes = (
        "xcron_cli",
        "xcron_libs.actions",
        "xcron_libs.sdk",
        "xcron_libs.services.cli_contracts",
        "xcron_libs.services.cli_mappers",
        "xcron_libs.services.cli_responses",
    )
    for module in RUNTIME_MODULES:
        imported = _imported_modules(module)
        assert not any(name.startswith(forbidden_prefixes) for name in imported), module


def test_services_package_initializer_does_not_aggregate_channels() -> None:
    initializer = REPOSITORY_ROOT / "libs" / "services" / "__init__.py"
    assert _imported_modules(initializer) == set()


def test_legacy_action_modules_are_capability_import_shims() -> None:
    for module in ACTION_SHIMS:
        imported = _imported_modules(module)
        assert imported, module
        assert all(name.startswith("xcron_libs.capabilities") for name in imported), module


def test_scheduler_registry_rejects_duplicate_and_unknown_identities() -> None:
    class First:
        name = "test"

    class Duplicate:
        name = "test"

    with pytest.raises(ValueError, match="duplicate scheduler backend: test"):
        SchedulerRegistry((First(), Duplicate()))

    registry = SchedulerRegistry((First(),))
    with pytest.raises(ValueError, match="unsupported scheduler backend: absent"):
        registry.require("absent")


def test_scheduler_runtime_options_normalize_direct_caller_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    options = SchedulerRuntimeOptions.create(
        state_root="state",
        launch_agents_dir=Path("agents"),
        launchctl_domain="gui/501",
        crontab_path="cron/tab",
        manage_launchctl=False,
        manage_crontab=False,
    )

    assert options.state_root == tmp_path / "state"
    assert options.launch_agents_dir == tmp_path / "agents"
    assert options.launchctl_domain == "gui/501"
    assert options.crontab_path == tmp_path / "cron" / "tab"
    assert options.manage_launchctl is False
    assert options.manage_crontab is False

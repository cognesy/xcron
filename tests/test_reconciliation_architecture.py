"""Mechanical checks for the scheduler adapter boundary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from xcron_libs.capabilities.reconciliation.api import SchedulerRegistry
from xcron_libs.capabilities.reconciliation.contracts import SchedulerRuntimeOptions


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_PACKAGE = "xcron_libs.capabilities"
ISOLATED_MODULES = (
    "agent_hooks",
    "jobs",
    "manifest",
    "operations",
    "reconciliation",
    "workspace",
)
AGENT_HOOKS_ROOT = f"{CAPABILITY_PACKAGE}.agent_hooks"
ADAPTER_ROOT = REPOSITORY_ROOT / "libs" / "capabilities" / "reconciliation" / "adapters"
BACKEND_MODULES = tuple(
    path for path in sorted(ADAPTER_ROOT.glob("*.py")) if path.name != "__init__.py"
)
CAPABILITY_MODULES = tuple(sorted((REPOSITORY_ROOT / "libs" / "capabilities").rglob("*.py")))
DOMAIN_MODULES = tuple(sorted((REPOSITORY_ROOT / "libs" / "domain").rglob("*.py")))
RUNTIME_MODULES = tuple(sorted((REPOSITORY_ROOT / "libs" / "runtime").rglob("*.py")))

def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def _public_surface_violations(source: str, *, filename: str = "<planted>") -> set[str]:
    """Return capability imports that bypass a module's ``api``/``contracts``."""

    tree = ast.parse(source, filename=filename)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                violations.update(_violations_for_dotted_path(alias.name))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            module = node.module
            owner = _module_owner(module)
            if owner is None:
                continue
            root = f"{CAPABILITY_PACKAGE}.{owner}"
            if module == root:
                # ``from <module> import x`` is only legal for the two surfaces.
                for alias in node.names:
                    if alias.name not in {"api", "contracts"}:
                        violations.add(f"{module}.{alias.name}")
            elif module in {f"{root}.api", f"{root}.contracts"}:
                for alias in node.names:
                    if alias.name.startswith("_"):
                        violations.add(f"{module}.{alias.name}")
            else:
                violations.add(module)
    return violations


def _module_owner(dotted: str) -> str | None:
    """Return the isolated capability module a dotted import path belongs to."""

    for name in ISOLATED_MODULES:
        root = f"{CAPABILITY_PACKAGE}.{name}"
        if dotted == root or dotted.startswith(f"{root}."):
            return name
    return None


def _violations_for_dotted_path(dotted: str) -> set[str]:
    owner = _module_owner(dotted)
    if owner is None:
        return set()
    root = f"{CAPABILITY_PACKAGE}.{owner}"
    if dotted in {f"{root}.api", f"{root}.contracts"}:
        return set()
    return {dotted}


def _module_roots(module: str) -> tuple[Path, ...]:
    """The implementation directory and the module-owned test lane.

    A module's own test lane is part of the module, so it may exercise private
    internals. Everything else in the repository may not.
    """

    return (
        REPOSITORY_ROOT / "libs" / "capabilities" / module,
        REPOSITORY_ROOT / "tests" / "modules" / module,
    )


def _source_files_outside(module: str) -> tuple[Path, ...]:
    """Every repository source file that is not part of the given module."""

    owned = _module_roots(module)
    this_file = Path(__file__).resolve()
    paths: list[Path] = []
    for root in ("libs", "apps", "tests"):
        for path in sorted((REPOSITORY_ROOT / root).rglob("*.py")):
            if path == this_file or any(root_dir in path.parents for root_dir in owned):
                continue
            paths.append(path)
    return tuple(paths)


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_public_surface_checker_has_planted_negative_examples(module: str) -> None:
    root = f"{CAPABILITY_PACKAGE}.{module}"
    forbidden = (
        f"import {root}._private",
        f"import {root}._private as shortcut",
        f"import {root}.implementation",
        f"from {root} import _private",
        f"from {root} import implementation as shortcut",
        f"from {root}._private import Thing",
        f"from {root}.implementation import Thing as Alias",
        f"from {root}.api import _private_helper",
    )
    allowed = (
        f"import {root}.api as module_api",
        f"import {root}.contracts",
        f"from {root} import api as module_api",
        f"from {root} import contracts",
        f"from {root}.api import public_callable",
        f"from {root}.contracts import PublicResult as Alias",
    )

    for source in forbidden:
        assert _public_surface_violations(source), source
    for source in allowed:
        assert _public_surface_violations(source) == set(), source


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_nothing_outside_a_capability_module_imports_below_its_surface(module: str) -> None:
    root = f"{CAPABILITY_PACKAGE}.{module}"
    for path in _source_files_outside(module):
        violations = {
            name
            for name in _public_surface_violations(
                path.read_text(encoding="utf-8"), filename=str(path)
            )
            if name.startswith(root)
        }
        assert not violations, (path.relative_to(REPOSITORY_ROOT), sorted(violations))


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_capability_package_initializer_does_not_aggregate(module: str) -> None:
    """The package root re-exports nothing; ``api``/``contracts`` are the surface."""

    initializer = REPOSITORY_ROOT / "libs" / "capabilities" / module / "__init__.py"
    assert _imported_modules(initializer) == set(), initializer


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_every_capability_module_declares_both_public_surfaces(module: str) -> None:
    module_root = REPOSITORY_ROOT / "libs" / "capabilities" / module
    for surface in ("api.py", "contracts.py"):
        path = module_root / surface
        assert path.is_file(), path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        exported = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        if surface == "api.py":
            assert "__all__" in exported, path


def test_agent_hooks_module_has_no_sibling_or_channel_imports() -> None:
    module_root = REPOSITORY_ROOT / "libs" / "capabilities" / "agent_hooks"
    own_modules = {"_claude", "_codex", "_paths", "contracts"}
    forbidden_prefixes = (
        "xcron_cli",
        "xcron_libs.sdk",
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


# The only permitted cross-module import edges, by module. This table is the
# dependency graph in `02-target-architecture.md`, enforced. The edge that is
# deliberately absent is `reconciliation -> operations`: reconciliation reports
# outcomes through its `OutcomeRecorder` port, and the composition root supplies
# the adapter. Adding an entry here is an architectural decision, not a fix.
DECLARED_MODULE_EDGES = {
    "agent_hooks": frozenset(),
    "jobs": frozenset({"manifest", "reconciliation"}),
    "manifest": frozenset({"workspace"}),
    "operations": frozenset({"reconciliation", "workspace"}),
    "reconciliation": frozenset({"manifest", "workspace"}),
    "workspace": frozenset(),
}


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_capability_modules_only_take_declared_cross_module_edges(module: str) -> None:
    allowed = DECLARED_MODULE_EDGES[module]
    module_root = REPOSITORY_ROOT / "libs" / "capabilities" / module

    for path in sorted(module_root.rglob("*.py")):
        for imported in _imported_modules(path):
            owner = _module_owner(imported)
            if owner is None or owner == module:
                continue
            assert owner in allowed, (path.relative_to(REPOSITORY_ROOT), imported)


def test_scheduler_adapters_do_not_import_actions_or_sdk() -> None:
    """Adapters receive leaf contracts, never their coordinating action results."""
    assert BACKEND_MODULES, "no scheduler adapters found"
    for module in BACKEND_MODULES:
        imported = _imported_modules(module)
        assert not any(name.startswith("xcron_libs.actions") for name in imported), module
        assert not any(name.startswith("xcron_libs.sdk") for name in imported), module


def test_scheduler_adapters_depend_on_the_port_not_the_use_cases() -> None:
    """An adapter implements `ports`; it must not see a use-case result type."""

    use_case_modules = {
        f"{CAPABILITY_PACKAGE}.reconciliation.{name}"
        for name in ("api", "contracts", "apply", "planning", "prune", "status", "inspect", "validation")
    }
    for module in BACKEND_MODULES:
        offenders = sorted(_imported_modules(module) & use_case_modules)
        assert not offenders, (module.relative_to(REPOSITORY_ROOT), offenders)


def test_reconciliation_owns_its_scheduler_adapters() -> None:
    """Phase 3 dissolved `libs/services/backends`; it must not come back."""

    assert not (REPOSITORY_ROOT / "libs" / "services" / "backends").exists()
    for name in ("wrapper_renderer.py", "state_store.py"):
        assert not (REPOSITORY_ROOT / "libs" / "services" / name).exists(), name
    assert not (REPOSITORY_ROOT / "libs" / "domain" / "diffing.py").exists()

    module_root = REPOSITORY_ROOT / "libs" / "capabilities" / "reconciliation"
    for relative in (
        "adapters/cron.py",
        "adapters/launchd.py",
        "adapters/process.py",
        "domain.py",
        "ports.py",
        "registry.py",
        "state_store.py",
        "wrapper.py",
    ):
        assert (module_root / relative).is_file(), relative


def test_domain_package_is_a_leaf_with_no_capability_dependency() -> None:
    """`libs/domain` holds manifest value types; diffing belongs to a module."""

    for path in sorted((REPOSITORY_ROOT / "libs" / "domain").rglob("*.py")):
        offenders = sorted(
            name for name in _imported_modules(path) if name.startswith(CAPABILITY_PACKAGE)
        )
        assert not offenders, (path.relative_to(REPOSITORY_ROOT), offenders)


def test_typer_shell_uses_the_sdk_not_action_implementations() -> None:
    imported = _imported_modules(REPOSITORY_ROOT / "apps" / "cli" / "typer_app.py")
    forbidden_prefixes = (
        "xcron_libs.actions",
        "xcron_libs.capabilities",
    )

    assert "xcron_libs" in imported
    assert not any(name.startswith(forbidden_prefixes) for name in imported)


def test_no_library_module_imports_the_cli_channel() -> None:
    """`xcron_cli` owns its projections; `libs/` may never reach back into it."""

    for path in sorted((REPOSITORY_ROOT / "libs").rglob("*.py")):
        imported = _imported_modules(path)
        offenders = sorted(
            name for name in imported if name == "xcron_cli" or name.startswith("xcron_cli.")
        )
        assert not offenders, (path.relative_to(REPOSITORY_ROOT), offenders)


def test_cli_projection_modules_live_in_the_cli_channel() -> None:
    """The projection cluster moved out of `libs/services` and stays out."""

    services_root = REPOSITORY_ROOT / "libs" / "services"
    for name in (
        "cli_contracts.py",
        "cli_responses.py",
        "cli_mappers.py",
        "axi_presenter.py",
        "toon_renderer.py",
        "tmux_renderer.py",
        "help_renderer.py",
    ):
        assert not (services_root / name).exists(), name

    cli_root = REPOSITORY_ROOT / "apps" / "cli"
    for relative in (
        "contracts.py",
        "responses.py",
        "mappers.py",
        "presenters/axi_presenter.py",
        "presenters/toon_renderer.py",
        "presenters/tmux_renderer.py",
        "presenters/help_renderer.py",
        "resources/help/root.md",
    ):
        assert (cli_root / relative).is_file(), relative


def test_capabilities_do_not_depend_on_the_cli_or_rendering_boundary() -> None:
    forbidden_prefixes = (
        "xcron_cli",
        "typer",
        "rich",
    )
    for module in CAPABILITY_MODULES:
        imported = _imported_modules(module)
        assert not any(name.startswith(forbidden_prefixes) for name in imported), module


def test_domain_does_not_depend_on_channels_or_application_layers() -> None:
    forbidden_prefixes = (
        "xcron_cli",
        "xcron_libs.actions",
        "xcron_libs.capabilities",
        "xcron_libs.runtime",
        "xcron_libs.sdk",
    )
    for module in DOMAIN_MODULES:
        imported = _imported_modules(module)
        assert not any(name.startswith(forbidden_prefixes) for name in imported), module


def test_runtime_is_composition_only_and_channel_independent() -> None:
    forbidden_prefixes = (
        "xcron_cli",
        "xcron_libs.actions",
        "xcron_libs.sdk",
    )
    for module in RUNTIME_MODULES:
        imported = _imported_modules(module)
        assert not any(name.startswith(forbidden_prefixes) for name in imported), module


def test_the_ownerless_service_and_infra_packages_are_gone() -> None:
    """`libs/services/` had 21 modules and no owner. It must not come back.

    Every file it held now belongs to exactly one module or to the shared leaf.
    A new file here would be a file with no owner again, which is the condition
    this whole refactor exists to remove.
    """
    assert not (REPOSITORY_ROOT / "libs" / "services").exists()
    assert not (REPOSITORY_ROOT / "libs" / "infra").exists()

    for path in sorted((REPOSITORY_ROOT / "libs").rglob("*.py")):
        for imported in _imported_modules(path):
            assert not imported.startswith("xcron_libs.services"), path
            assert not imported.startswith("xcron_libs.infra"), path


SHARED_ROOT = REPOSITORY_ROOT / "libs" / "shared"
SHARED_MODULES = tuple(
    path for path in sorted(SHARED_ROOT.rglob("*.py")) if path.name != "__init__.py"
)


def test_shared_is_a_strict_leaf() -> None:
    """`libs/shared/` may be imported by anything and may import almost nothing.

    That asymmetry is what makes it safe. The moment it can import a capability
    it stops being a leaf and becomes a second, undeclared coupling point.
    """
    assert SHARED_MODULES, "libs/shared must not be empty"

    forbidden_prefixes = (
        "xcron_cli",
        "xcron_libs.actions",
        "xcron_libs.capabilities",
        "xcron_libs.runtime",
        "xcron_libs.sdk",
        "typer",
        "rich",
    )
    for path in SHARED_MODULES:
        imported = _imported_modules(path)
        assert not any(name.startswith(forbidden_prefixes) for name in imported), path


def test_every_packaged_resource_lives_inside_the_module_that_reads_it() -> None:
    """A resource directory is owned state; it ships with its one reader."""
    from xcron_libs.capabilities.manifest.contracts import SCHEMA_PACKAGE
    from xcron_libs.shared.logging_config import LOGGING_PACKAGE

    assert SCHEMA_PACKAGE == "xcron_libs.capabilities.manifest.resources.schemas"
    assert LOGGING_PACKAGE == "xcron_libs.shared.resources.logging"

    assert (
        REPOSITORY_ROOT
        / "libs/capabilities/manifest/resources/schemas/schedules.schema.yaml"
    ).is_file()
    assert (REPOSITORY_ROOT / "libs/shared/resources/logging/default.yaml").is_file()
    assert not (REPOSITORY_ROOT / "resources" / "schemas").exists()
    assert not (REPOSITORY_ROOT / "resources" / "logging").exists()


def test_reconciliation_reports_outcomes_through_a_port_it_owns() -> None:
    """Reconciliation must not construct another module's state writer.

    Before Phase 4 two capabilities wrote `metrics.json`. Operations is now the
    single writer; reconciliation names only the port, and the composition root
    is the one place the two meet.
    """
    reconciliation_root = REPOSITORY_ROOT / "libs" / "capabilities" / "reconciliation"
    for path in sorted(reconciliation_root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "MetricsService" not in source, path
        for imported in _imported_modules(path):
            assert not imported.startswith(f"{CAPABILITY_PACKAGE}.operations"), path

    composition = REPOSITORY_ROOT / "libs" / "runtime" / "composition.py"
    imported = _imported_modules(composition)
    assert f"{CAPABILITY_PACKAGE}.operations.api" in imported
    assert f"{CAPABILITY_PACKAGE}.reconciliation.contracts" in imported


def test_the_metrics_store_has_exactly_one_writing_module() -> None:
    """`MetricsService` may only be named inside the module that owns the file."""
    operations_root = REPOSITORY_ROOT / "libs" / "capabilities" / "operations"
    writers = {
        path
        for path in sorted((REPOSITORY_ROOT / "libs").rglob("*.py"))
        if "MetricsService" in path.read_text(encoding="utf-8")
    }
    assert writers, "the metrics store disappeared; update this contract"
    assert all(path.is_relative_to(operations_root) for path in writers), sorted(
        str(path) for path in writers
    )


CONFIGURATION_ROOT = REPOSITORY_ROOT / "libs" / "configuration"
CONFIGURATION_MODULES = tuple(sorted(CONFIGURATION_ROOT.rglob("*.py")))

#: Files allowed to name `os.environ` or `os.getenv`. Everything else receives
#: settings as values from the composition root.
DECLARED_ENVIRONMENT_READERS = {
    # Composes settings from the published `XCRON_*` variables.
    "libs/configuration/loader.py",
    # Workspace identity selects *which* config files are read, so it cannot
    # itself come from one.
    "libs/capabilities/workspace/resolver.py",
    # Passes the environment it was handed down to the two above.
    "libs/runtime/composition.py",
    # Logging bootstraps before a runtime exists; see the Phase 5 record.
    "libs/shared/logging_config.py",
    # Emitted into generated wrapper scripts as text, not read in this process.
    "libs/capabilities/reconciliation/wrapper.py",
}


def test_only_declared_modules_read_the_environment() -> None:
    """Settings are resolved once. A second reader is free to disagree.

    Adding a file here is an architectural decision: it means some code below
    the composition root now has its own opinion about the environment, and
    two opinions is exactly the bug this phase removed.
    """
    readers = set()
    for root in ("libs", "apps"):
        for path in sorted((REPOSITORY_ROOT / root).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "os.environ" in source or "os.getenv" in source:
                readers.add(str(path.relative_to(REPOSITORY_ROOT)))

    assert readers == DECLARED_ENVIRONMENT_READERS


def test_the_configuration_library_has_exactly_one_importer_of_xcfg() -> None:
    """`xcfg` is a mechanism, reached through xcron's own surface or not at all."""
    importers = {
        str(path.relative_to(REPOSITORY_ROOT))
        for root in ("libs", "apps", "tests")
        for path in sorted((REPOSITORY_ROOT / root).rglob("*.py"))
        if any(name == "xcfg" or name.startswith("xcfg.") for name in _imported_modules(path))
    }

    assert importers == {"libs/configuration/loader.py"}


def test_configuration_is_a_leaf_that_no_capability_depends_on() -> None:
    """Settings arrive as values. A capability importing the loader would be
    resolving configuration a second time, at a different moment, from a
    different environment."""
    forbidden_prefixes = (
        "xcron_cli",
        "xcron_libs.actions",
        "xcron_libs.capabilities",
        "xcron_libs.runtime",
        "xcron_libs.sdk",
    )
    assert CONFIGURATION_MODULES, "libs/configuration must not be empty"
    for path in CONFIGURATION_MODULES:
        imported = _imported_modules(path)
        assert not any(name.startswith(forbidden_prefixes) for name in imported), path

    for path in sorted((REPOSITORY_ROOT / "libs" / "capabilities").rglob("*.py")):
        offenders = sorted(
            name for name in _imported_modules(path) if name.startswith("xcron_libs.configuration")
        )
        assert not offenders, (path.relative_to(REPOSITORY_ROOT), offenders)


def test_the_composition_root_is_the_only_place_settings_are_loaded() -> None:
    loaders = {
        str(path.relative_to(REPOSITORY_ROOT))
        for root in ("libs", "apps")
        for path in sorted((REPOSITORY_ROOT / root).rglob("*.py"))
        if "xcron_libs.configuration.api" in _imported_modules(path)
    }

    assert loaders == {"libs/runtime/composition.py"}


def test_the_home_module_folded_into_workspace() -> None:
    """One module owned workspace layout and another owned creating one."""
    assert not (REPOSITORY_ROOT / "libs" / "capabilities" / "home").exists()

    workspace_root = REPOSITORY_ROOT / "libs" / "capabilities" / "workspace"
    for relative in ("initializer.py", "marker.py", "paths.py", "resolver.py"):
        assert (workspace_root / relative).is_file(), relative


def test_the_actions_facade_is_gone() -> None:
    """The shim existed to let callers move; they have all moved.

    Kept any longer it becomes a second, flatter name for every capability —
    two ways to reach the same function, one of which says nothing about who
    owns it. Every caller now names the owning module's `api`.
    """
    assert not (REPOSITORY_ROOT / "libs" / "actions").exists()

    for path in sorted((REPOSITORY_ROOT / "libs").rglob("*.py")):
        for imported in _imported_modules(path):
            assert not imported.startswith("xcron_libs.actions"), path


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

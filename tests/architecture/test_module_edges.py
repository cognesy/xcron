"""Which module may depend on which, and the one edge that must stay absent.

Import Linter's layers contract covers the same DAG from the other side. This
lane keeps the declared edge table readable as a table — the failure names the
module, the file, and the import, which is the information needed to decide
whether the edge is a mistake or a decision.
"""

from __future__ import annotations

import pytest

from tests.architecture.scanner import (
    CAPABILITY_PACKAGE,
    CAPABILITY_ROOT,
    DECLARED_MODULE_EDGES,
    ISOLATED_MODULES,
    REPOSITORY_ROOT,
    imported_modules,
    module_owner,
    source_files,
)

ADAPTER_ROOT = CAPABILITY_ROOT / "reconciliation" / "adapters"
BACKEND_MODULES = tuple(
    path for path in sorted(ADAPTER_ROOT.glob("*.py")) if path.name != "__init__.py"
)


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_capability_modules_only_take_declared_cross_module_edges(module: str) -> None:
    allowed = DECLARED_MODULE_EDGES[module]

    for path in sorted((CAPABILITY_ROOT / module).rglob("*.py")):
        for imported in imported_modules(path):
            owner = module_owner(imported)
            if owner is None or owner == module:
                continue
            assert owner in allowed, (path.relative_to(REPOSITORY_ROOT), imported)


def test_scheduler_adapters_do_not_import_a_use_case_or_the_sdk() -> None:
    """Adapters receive leaf contracts, never their coordinating results."""
    assert BACKEND_MODULES, "no scheduler adapters found"
    for module in BACKEND_MODULES:
        imported = imported_modules(module)
        assert not any(name.startswith("xcron_libs.sdk") for name in imported), module


def test_scheduler_adapters_depend_on_the_port_not_the_use_cases() -> None:
    """An adapter implements `ports`; it must not see a use-case result type."""
    use_case_modules = {
        f"{CAPABILITY_PACKAGE}.reconciliation.{name}"
        for name in (
            "api",
            "contracts",
            "apply",
            "planning",
            "prune",
            "status",
            "inspect",
            "validation",
        )
    }
    for module in BACKEND_MODULES:
        offenders = sorted(imported_modules(module) & use_case_modules)
        assert not offenders, (module.relative_to(REPOSITORY_ROOT), offenders)


def test_reconciliation_owns_its_scheduler_adapters() -> None:
    """Phase 3 dissolved `libs/services/backends`; it must not come back."""
    assert not (REPOSITORY_ROOT / "libs" / "services" / "backends").exists()
    assert not (REPOSITORY_ROOT / "libs" / "domain" / "diffing.py").exists()

    module_root = CAPABILITY_ROOT / "reconciliation"
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


def test_reconciliation_reports_outcomes_through_a_port_it_owns() -> None:
    """Reconciliation must not construct another module's state writer.

    Before Phase 4 two capabilities wrote `metrics.json`. Operations is now the
    single writer; reconciliation names only the port, and the composition root
    is the one place the two meet.
    """
    for path in sorted((CAPABILITY_ROOT / "reconciliation").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "MetricsService" not in source, path
        for imported in imported_modules(path):
            assert not imported.startswith(f"{CAPABILITY_PACKAGE}.operations"), path

    composition = REPOSITORY_ROOT / "libs" / "runtime" / "composition.py"
    imported = imported_modules(composition)
    assert f"{CAPABILITY_PACKAGE}.operations.api" in imported
    assert f"{CAPABILITY_PACKAGE}.reconciliation.contracts" in imported


def test_the_metrics_store_has_exactly_one_writing_module() -> None:
    """`MetricsService` may only be named inside the module that owns the file."""
    operations_root = CAPABILITY_ROOT / "operations"
    writers = {
        path
        for path in source_files("libs")
        if "MetricsService" in path.read_text(encoding="utf-8")
    }
    assert writers, "the metrics store disappeared; update this contract"
    assert all(path.is_relative_to(operations_root) for path in writers), sorted(
        str(path) for path in writers
    )

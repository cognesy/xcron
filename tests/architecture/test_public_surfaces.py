"""A module is what it hides, and `api`/`contracts` is where it stops hiding.

An import graph cannot express this rule: `jobs -> manifest` is a legal edge
either way, and the whole question is whether it landed on `manifest.api` or on
`manifest._editor`. So these tests read the import *statement*, not the edge.
"""

from __future__ import annotations

import ast

import pytest

from tests.architecture.scanner import (
    CAPABILITY_PACKAGE,
    CAPABILITY_ROOT,
    ISOLATED_MODULES,
    REPOSITORY_ROOT,
    imported_modules,
    public_surface_violations,
    source_files_outside,
)


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_public_surface_checker_has_planted_negative_examples(module: str) -> None:
    """A checker nobody has seen fail is a checker nobody knows works.

    Each forbidden form here has been observed to slip past a naive scanner:
    aliased imports, submodule imports, and root-level `from` imports all reach
    the same private code by different syntax.
    """
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
        assert public_surface_violations(source), source
    for source in allowed:
        assert public_surface_violations(source) == set(), source


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_nothing_outside_a_capability_module_imports_below_its_surface(module: str) -> None:
    root = f"{CAPABILITY_PACKAGE}.{module}"
    for path in source_files_outside(module):
        violations = {
            name
            for name in public_surface_violations(
                path.read_text(encoding="utf-8"), filename=str(path)
            )
            if name.startswith(root)
        }
        assert not violations, (path.relative_to(REPOSITORY_ROOT), sorted(violations))


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_capability_package_initializer_does_not_aggregate(module: str) -> None:
    """The package root re-exports nothing; `api`/`contracts` are the surface.

    An aggregating `__init__.py` quietly makes every name importable from the
    package root, which is a third surface nobody declared.
    """
    initializer = CAPABILITY_ROOT / module / "__init__.py"
    assert imported_modules(initializer) == set(), initializer


@pytest.mark.parametrize("module", ISOLATED_MODULES)
def test_every_capability_module_declares_both_public_surfaces(module: str) -> None:
    module_root = CAPABILITY_ROOT / module
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
    """The reference Level 1 module: standard library, and its own files.

    Checked separately from the edge table because the interesting part is the
    relative-import form, which the dotted-path scanner cannot see.
    """
    module_root = CAPABILITY_ROOT / "agent_hooks"
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
                    names = [alias.name for alias in node.names]
                    assert not any(name.startswith(forbidden_prefixes) for name in names), path
                continue
            if node.level:
                assert node.level == 1, path
                assert node.module in own_modules, (path, node.module)
            elif node.module:
                assert not node.module.startswith(forbidden_prefixes), (path, node.module)

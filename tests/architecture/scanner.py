"""The AST scanner the architecture tests share.

Import Linter states the dependency graph and checks it. What it cannot say is
*which file inside a module* another module reached for, or which files are
allowed to read the environment — a graph knows edges, not the difference
between a module's public surface and its insides. That is what this scanner is
for, and it is why both gates exist.

Reading imports out of source rather than importing anything keeps the checks
honest about files that are never loaded and about a module that was deleted.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CAPABILITY_PACKAGE = "xcron_libs.capabilities"
CAPABILITY_ROOT = REPOSITORY_ROOT / "libs" / "capabilities"

#: Every capability that owns a decision behind an `api`/`contracts` pair.
ISOLATED_MODULES = (
    "agent_hooks",
    "jobs",
    "manifest",
    "operations",
    "reconciliation",
    "workspace",
)

#: The only permitted cross-module import edges, by module. This table is the
#: dependency graph in `02-target-architecture.md`, enforced. The edge that is
#: deliberately absent is `reconciliation -> operations`: reconciliation reports
#: outcomes through its `OutcomeRecorder` port, and the composition root
#: supplies the adapter. Adding an entry here is an architectural decision, not
#: a fix.
DECLARED_MODULE_EDGES = {
    "agent_hooks": frozenset(),
    "jobs": frozenset({"manifest", "reconciliation"}),
    "manifest": frozenset({"workspace"}),
    "operations": frozenset({"reconciliation", "workspace"}),
    "reconciliation": frozenset({"manifest", "workspace"}),
    "workspace": frozenset(),
}


def source_files(*roots: str) -> tuple[Path, ...]:
    """Every Python file under the named repository directories."""
    return tuple(
        path for root in roots for path in sorted((REPOSITORY_ROOT / root).rglob("*.py"))
    )


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def imports_anything_matching(path: Path, prefixes: tuple[str, ...]) -> list[str]:
    """The offending import names, so a failure says which one and not just that."""
    return sorted(name for name in imported_modules(path) if name.startswith(prefixes))


def module_owner(dotted: str) -> str | None:
    """Return the isolated capability module a dotted import path belongs to."""
    for name in ISOLATED_MODULES:
        root = f"{CAPABILITY_PACKAGE}.{name}"
        if dotted == root or dotted.startswith(f"{root}."):
            return name
    return None


def public_surface_violations(source: str, *, filename: str = "<planted>") -> set[str]:
    """Return capability imports that bypass a module's ``api``/``contracts``."""
    tree = ast.parse(source, filename=filename)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                violations.update(_violations_for_dotted_path(alias.name))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            module = node.module
            owner = module_owner(module)
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


def _violations_for_dotted_path(dotted: str) -> set[str]:
    owner = module_owner(dotted)
    if owner is None:
        return set()
    root = f"{CAPABILITY_PACKAGE}.{owner}"
    if dotted in {f"{root}.api", f"{root}.contracts"}:
        return set()
    return {dotted}


def module_roots(module: str) -> tuple[Path, ...]:
    """The implementation directory and the module-owned test lane.

    A module's own test lane is part of the module, so it may exercise private
    internals. Everything else in the repository may not.
    """
    return (
        CAPABILITY_ROOT / module,
        REPOSITORY_ROOT / "tests" / "modules" / module,
    )


def source_files_outside(module: str) -> tuple[Path, ...]:
    """Every repository source file that is not part of the given module."""
    owned = module_roots(module)
    return tuple(
        path
        for path in source_files("libs", "apps", "tests")
        if not any(root in path.parents for root in owned)
    )

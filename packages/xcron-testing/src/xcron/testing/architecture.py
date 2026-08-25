"""Layout-agnostic structural checks for the xcron package workspace."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArchitectureViolation:
    """One source-level contract violation discovered in a package tree."""

    rule: str
    path: Path
    detail: str


def source_roots(repository_root: Path) -> tuple[Path, ...]:
    """Return every installed-package source root in a workspace checkout."""
    candidates = [repository_root / "src" / "xcron"]
    for parent in ("packages", "capabilities"):
        candidates.extend((repository_root / parent).glob("*/src/xcron"))
    return tuple(sorted((path for path in candidates if path.is_dir()), key=str))


def check_package_boundaries(repository_root: Path) -> tuple[ArchitectureViolation, ...]:
    """Scan every package root without assuming which providers are installed.

    It guards three edges that Import Linter cannot see once providers move
    into independently built wheels: the generic kernel may not name product
    capabilities; one provider may not import another provider at all; and
    provider core may not import a terminal channel.  Provider collaboration
    is restricted to the neutral ``xcron.contracts`` vocabulary and host ports.
    """
    violations: list[ArchitectureViolation] = []
    for root in source_roots(repository_root):
        for source in root.rglob("*.py"):
            violations.extend(_file_violations(source, root))
    return tuple(violations)


def _file_violations(source: Path, source_root: Path) -> list[ArchitectureViolation]:
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    except SyntaxError as error:
        return [ArchitectureViolation("syntax", source, str(error))]
    imports = _imports(tree)
    relative = source.relative_to(source_root)
    violations: list[ArchitectureViolation] = []
    if relative.parts[:1] == ("kernel",):
        for module in imports:
            if module == "xcron.capabilities" or module.startswith("xcron.capabilities."):
                violations.append(ArchitectureViolation("kernel-product", source, module))

    provider_name = _provider_name(source_root, relative)
    if provider_name is None:
        return violations
    for module in imports:
        if module == "xcron_cli" or module.startswith("xcron_cli."):
            violations.append(ArchitectureViolation("provider-channel", source, module))
        peer = _peer_provider(module, provider_name)
        if peer is not None:
            violations.append(ArchitectureViolation("provider-peer-import", source, peer))
    return violations


def _imports(tree: ast.AST) -> tuple[str, ...]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    return tuple(names)


def _provider_name(source_root: Path, relative: Path) -> str | None:
    """Return the provider's capability name only for external provider wheels."""
    if source_root.parents[2].name != "capabilities":
        return None
    if relative.parts[:1] != ("capabilities",) or len(relative.parts) < 2:
        return None
    return relative.parts[1]


def _peer_provider(module: str, provider_name: str) -> str | None:
    prefix = "xcron.capabilities."
    if not module.startswith(prefix):
        return None
    parts = module.split(".")
    if len(parts) < 3 or parts[2] == provider_name:
        return None
    return module

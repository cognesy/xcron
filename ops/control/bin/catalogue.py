"""Validate and operate xcron's local operations catalogue."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator
import yaml


ROOT = Path(__file__).resolve().parents[3]
OPS = ROOT / "ops"
SCHEMA = OPS / "control" / "schema"
CAPABILITY_NAME = "capability.yaml"
RECIPE = re.compile(r"^([a-z][a-z0-9-]*)(?:\s+[^:]+)?:\s*$")
PEER_PRIVATE_PATH = re.compile(r"(?:^|[\s\"'])ops/([a-z][a-z0-9-]*)/(?:bin|tests)/")


@dataclass(frozen=True)
class Diagnostic:
    rule: str
    message: str
    path: Path | None = None

    def render(self, root: Path) -> str:
        location = ""
        if self.path is not None:
            location = f" ({self.path.relative_to(root)})"
        return f"{self.rule}: {self.message}{location}"


@dataclass(frozen=True)
class Capability:
    root: Path
    manifest_path: Path
    manifest: Mapping[str, Any]

    @property
    def identifier(self) -> str:
        return str(self.manifest["id"])

    @property
    def provides(self) -> list[str]:
        return list(self.manifest["provides"])

    @property
    def commands(self) -> list[Mapping[str, Any]]:
        return list(self.manifest["commands"])

    @property
    def requires(self) -> list[str]:
        return list(self.manifest["requires"]["capabilities"])

    @property
    def owns(self) -> list[str]:
        return list(self.manifest["owns"])

    @property
    def skills(self) -> list[Mapping[str, str]]:
        return list(self.manifest["skills"])


def _load(path: Path) -> Mapping[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = yaml.safe_load(source)
    if not isinstance(value, Mapping):
        raise ValueError(f"expected a mapping in {path}")
    return value


def _schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(_load(SCHEMA / name))


def discover(ops_root: Path = OPS) -> list[Capability]:
    capabilities: list[Capability] = []
    for manifest_path in sorted(ops_root.glob(f"*/{CAPABILITY_NAME}")):
        capabilities.append(
            Capability(
                root=manifest_path.parent,
                manifest_path=manifest_path,
                manifest=_load(manifest_path),
            )
        )
    return capabilities


def _schema_diagnostics(
    validator: Draft202012Validator,
    value: Mapping[str, Any],
    path: Path,
    rule: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for error in sorted(validator.iter_errors(value), key=str):
        location = ".".join(str(part) for part in error.absolute_path) or "document"
        diagnostics.append(Diagnostic(rule, f"{location}: {error.message}", path))
    return diagnostics


def _recipe_names(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = RECIPE.match(line)
        if match:
            names.add(match.group(1))
    return names


def _ops_files(ops_root: Path) -> list[Path]:
    return sorted(
        path
        for path in ops_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


def _matches(pattern: str, path: Path, project_root: Path) -> bool:
    return fnmatchcase(path.relative_to(project_root).as_posix(), pattern)


def _cycles(graph: Mapping[str, Iterable[str]]) -> list[str]:
    active: set[str] = set()
    visited: set[str] = set()
    cycles: list[str] = []

    def visit(node: str, trail: list[str]) -> None:
        if node in active:
            cycles.append(" -> ".join([*trail, node]))
            return
        if node in visited:
            return
        active.add(node)
        for target in graph[node]:
            if target in graph:
                visit(target, [*trail, node])
        active.remove(node)
        visited.add(node)

    for identifier in graph:
        visit(identifier, [])
    return cycles


def _declaration_diagnostics(capability: Capability) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    declarations = {
        "owns": set(capability.manifest["owns"]),
        "reads": set(capability.manifest["reads"]),
        "generates": set(capability.manifest["generates"]),
    }
    for left, right in (("owns", "reads"), ("owns", "generates"), ("reads", "generates")):
        for overlap in sorted(declarations[left] & declarations[right]):
            diagnostics.append(
                Diagnostic(
                    "ownership",
                    f"{overlap!r} is declared as both {left} and {right}",
                    capability.manifest_path,
                )
            )
    return diagnostics


def _product_boundary_diagnostics(project_root: Path) -> list[Diagnostic]:
    source_root = project_root / "src" / "xcron"
    diagnostics: list[Diagnostic] = []
    if not source_root.is_dir():
        return diagnostics
    for source in source_root.rglob("*.py"):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except (OSError, SyntaxError) as error:
            diagnostics.append(Diagnostic("product-boundary", str(error), source))
            continue
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.append(node.module)
        for name in imported:
            if name == "ops" or name.startswith("ops.") or name.startswith("xcron.ops"):
                diagnostics.append(
                    Diagnostic("product-boundary", f"product code imports operations module {name!r}", source)
                )
    return diagnostics


def _peer_private_path_diagnostics(capabilities: Iterable[Capability]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for capability in capabilities:
        for path in capability.root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".sh", ".js", ".mjs"}:
                continue
            for peer in PEER_PRIVATE_PATH.findall(path.read_text(encoding="utf-8")):
                if peer != capability.identifier:
                    diagnostics.append(
                        Diagnostic(
                            "peer-boundary",
                            f"operation reaches into {peer!r} private bin/tests path",
                            path,
                        )
                    )
    return diagnostics


def validate(ops_root: Path = OPS) -> list[Diagnostic]:
    project_root = ops_root.parent
    diagnostics: list[Diagnostic] = []
    try:
        index = _load(ops_root / "ops.yaml")
    except (OSError, ValueError, yaml.YAMLError) as error:
        return [Diagnostic("catalogue", str(error), ops_root / "ops.yaml")]

    diagnostics.extend(
        _schema_diagnostics(_schema("ops.v1.yaml"), index, ops_root / "ops.yaml", "schema")
    )
    try:
        capabilities = discover(ops_root)
    except (OSError, ValueError, yaml.YAMLError) as error:
        return [*diagnostics, Diagnostic("catalogue", str(error), ops_root)]

    if not capabilities:
        diagnostics.append(Diagnostic("catalogue", "no capability manifests found", ops_root))
        return diagnostics

    for capability in capabilities:
        diagnostics.extend(
            _schema_diagnostics(
                _schema("capability.v1.yaml"),
                capability.manifest,
                capability.manifest_path,
                "schema",
            )
        )
        diagnostics.extend(_declaration_diagnostics(capability))

    identifiers = [capability.identifier for capability in capabilities]
    by_id = {capability.identifier: capability for capability in capabilities}
    if len(by_id) != len(capabilities):
        diagnostics.append(Diagnostic("identity", "capability ids must be unique"))

    for capability in capabilities:
        if capability.root.name != capability.identifier:
            diagnostics.append(
                Diagnostic(
                    "identity",
                    f"directory {capability.root.name!r} must match id {capability.identifier!r}",
                    capability.manifest_path,
                )
            )
        for required_asset in ("README.md", "justfile"):
            if not (capability.root / required_asset).is_file():
                diagnostics.append(
                    Diagnostic(
                        "layout",
                        f"missing required asset {required_asset}",
                        capability.root,
                    )
                )

        local_owner = f"ops/{capability.identifier}/**"
        if local_owner not in capability.owns:
            diagnostics.append(
                Diagnostic(
                    "ownership",
                    f"must own its local package with {local_owner}",
                    capability.manifest_path,
                )
            )

        justfile = capability.root / "justfile"
        recipes = _recipe_names(justfile) if justfile.is_file() else set()
        if "default" not in recipes:
            diagnostics.append(
                Diagnostic("commands", "justfile must expose safe default recipe", justfile)
            )
        for command in capability.commands:
            name = str(command["name"])
            if name not in recipes:
                diagnostics.append(
                    Diagnostic(
                        "commands",
                        f"declared command {name!r} has no local Just recipe",
                        justfile,
                    )
                )
        for skill in capability.skills:
            skill_path = capability.root / "skills" / skill["name"] / "SKILL.md"
            if not skill_path.is_file():
                diagnostics.append(
                    Diagnostic("skills", f"missing declared skill {skill['name']!r}", skill_path)
                )

    available = set(identifiers)
    for capability in capabilities:
        for dependency in capability.requires:
            if dependency not in available:
                diagnostics.append(
                    Diagnostic(
                        "dependencies",
                        f"unknown capability dependency {dependency!r}",
                        capability.manifest_path,
                    )
                )
    graph = {capability.identifier: capability.requires for capability in capabilities}
    for cycle in _cycles(graph):
        diagnostics.append(Diagnostic("dependencies", f"cycle: {cycle}"))

    providers = index.get("active", {})
    for service, provider in providers.items():
        capability = by_id.get(provider)
        if capability is None:
            diagnostics.append(
                Diagnostic("providers", f"{service!r} selects unknown {provider!r}", ops_root / "ops.yaml")
            )
        elif service not in capability.provides:
            diagnostics.append(
                Diagnostic(
                    "providers",
                    f"{provider!r} does not provide {service!r}",
                    ops_root / "ops.yaml",
                )
            )

    for path in _ops_files(ops_root):
        owners = [
            capability.identifier
            for capability in capabilities
            if any(_matches(pattern, path, project_root) for pattern in capability.owns)
        ]
        if len(owners) != 1:
            diagnostics.append(
                Diagnostic(
                    "ownership",
                    f"expected exactly one owner, found {owners or 'none'}",
                    path,
                )
            )
    diagnostics.extend(_product_boundary_diagnostics(project_root))
    diagnostics.extend(_peer_private_path_diagnostics(capabilities))
    return diagnostics


def render_list(ops_root: Path = OPS) -> str:
    rows = []
    for capability in discover(ops_root):
        rows.append(f"{capability.identifier:<14} {capability.manifest['description']}")
    return "\n".join(rows)


def route(arguments: list[str], ops_root: Path = OPS) -> int:
    """Run a declared operation route without deriving a path from user input."""
    diagnostics = validate(ops_root)
    if diagnostics:
        for diagnostic in diagnostics:
            print(diagnostic.render(ops_root.parent), file=sys.stderr)
        return 1

    if not arguments or arguments == ["list"]:
        print(render_list(ops_root))
        return 0
    if arguments[0] == "list":
        print("route: 'list' does not accept additional arguments", file=sys.stderr)
        return 2

    capability_id, *remaining = arguments
    capabilities = {capability.identifier: capability for capability in discover(ops_root)}
    capability = capabilities.get(capability_id)
    if capability is None:
        print(f"route: unknown operations capability {capability_id!r}", file=sys.stderr)
        return 2

    command = remaining[0] if remaining else "default"
    command_arguments = remaining[1:]
    declared = {str(item["name"]) for item in capability.commands}
    if command != "default" and command not in declared:
        available = ", ".join(["default", *sorted(declared)])
        print(
            f"route: {capability_id!r} does not declare command {command!r}; "
            f"available: {available}",
            file=sys.stderr,
        )
        return 2

    completed = subprocess.run(
        [
            "just",
            "--justfile",
            str(capability.root / "justfile"),
            command,
            *command_arguments,
        ],
        check=False,
    )
    return completed.returncode


def _steps(ops_root: Path, lane: str) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = []
    for capability in discover(ops_root):
        for command in capability.commands:
            if command.get("aggregate") == lane:
                steps.append((capability.identifier, str(command["name"])))
    return steps


def run_lane(ops_root: Path, lane: str) -> int:
    diagnostics = validate(ops_root)
    if diagnostics:
        for diagnostic in diagnostics:
            print(diagnostic.render(ops_root.parent), file=sys.stderr)
        return 1
    for capability, command in _steps(ops_root, lane):
        completed = subprocess.run(
            ["just", "ops", capability, command],
            cwd=ops_root.parent,
            check=False,
        )
        if completed.returncode:
            return completed.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate")
    subcommands.add_parser("list")
    aggregate = subcommands.add_parser("aggregate")
    aggregate.add_argument("lane", choices=("check", "test"))
    routed = subcommands.add_parser("route")
    routed.add_argument("arguments", nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)

    if arguments.command == "validate":
        diagnostics = validate()
        for diagnostic in diagnostics:
            print(diagnostic.render(ROOT), file=sys.stderr)
        if diagnostics:
            return 1
        print(f"validated {len(discover())} operations capabilities")
        return 0
    if arguments.command == "list":
        print(render_list())
        return 0
    if arguments.command == "route":
        return route(arguments.arguments)
    return run_lane(OPS, arguments.lane)


if __name__ == "__main__":
    raise SystemExit(main())

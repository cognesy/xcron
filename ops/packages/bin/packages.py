"""Discover and safely delegate local workspace package operations."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOTS = ("packages", "capabilities")
REQUIRED_RECIPES = frozenset({"default", "list", "doctor", "check", "test", "build"})
RECIPE = re.compile(r"^([a-z][a-z0-9-]*)(?:\s+[^:]+)?:\s*$")


@dataclass(frozen=True)
class Distribution:
    name: str
    root: Path
    justfile: Path


@dataclass(frozen=True)
class Diagnostic:
    message: str
    path: Path

    def render(self, root: Path) -> str:
        return f"packages: {self.message} ({self.path.relative_to(root)})"


def _directories(root: Path) -> list[Path]:
    directories: list[Path] = []
    for relative_root in PACKAGE_ROOTS:
        package_root = root / relative_root
        if not package_root.is_dir():
            continue
        directories.extend(path for path in package_root.iterdir() if path.is_dir())
    return sorted(directories)


def _recipe_names(path: Path) -> set[str]:
    return {
        match.group(1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if (match := RECIPE.match(line))
    }


def _descriptor_diagnostics(directory: Path) -> list[Diagnostic]:
    """Validate the small metadata contract every workspace distribution owns."""
    descriptor_path = directory / "capability.toml"
    if not descriptor_path.is_file():
        return [Diagnostic("missing capability.toml", directory)]
    try:
        descriptor = tomllib.loads(descriptor_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [Diagnostic(f"invalid capability.toml: {error}", descriptor_path)]

    package = descriptor.get("package")
    operations = descriptor.get("operations")
    diagnostics: list[Diagnostic] = []
    if not isinstance(package, dict) or not isinstance(package.get("kind"), str) or not package["kind"]:
        diagnostics.append(Diagnostic("capability.toml [package].kind must be a non-empty string", descriptor_path))
    if not isinstance(operations, dict):
        diagnostics.append(Diagnostic("capability.toml must declare [operations]", descriptor_path))
        return diagnostics
    if operations.get("justfile") != "justfile":
        diagnostics.append(Diagnostic("capability.toml [operations].justfile must be 'justfile'", descriptor_path))
    required = operations.get("required_recipes")
    if not isinstance(required, list) or set(required) != REQUIRED_RECIPES:
        diagnostics.append(
            Diagnostic(
                "capability.toml [operations].required_recipes must name the local routes",
                descriptor_path,
            )
        )
    return diagnostics


def discover(root: Path = ROOT) -> tuple[list[Distribution], list[Diagnostic]]:
    distributions: list[Distribution] = []
    diagnostics: list[Diagnostic] = []
    names: set[str] = set()
    for directory in _directories(root):
        metadata_path = directory / "pyproject.toml"
        if not metadata_path.is_file():
            diagnostics.append(Diagnostic("missing pyproject.toml", directory))
            continue
        try:
            metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
            project = metadata.get("project")
            name = project.get("name") if isinstance(project, dict) else None
        except (OSError, tomllib.TOMLDecodeError) as error:
            diagnostics.append(Diagnostic(f"invalid pyproject.toml: {error}", metadata_path))
            continue
        if not isinstance(name, str) or not name:
            diagnostics.append(Diagnostic("[project].name must be a non-empty string", metadata_path))
            continue
        if name in names:
            diagnostics.append(Diagnostic(f"duplicate distribution name {name!r}", metadata_path))
            continue
        names.add(name)

        descriptor_diagnostics = _descriptor_diagnostics(directory)
        if descriptor_diagnostics:
            diagnostics.extend(descriptor_diagnostics)
            continue

        justfile = directory / "justfile"
        if not justfile.is_file():
            diagnostics.append(Diagnostic("missing local justfile", directory))
            continue
        missing = REQUIRED_RECIPES - _recipe_names(justfile)
        if missing:
            diagnostics.append(
                Diagnostic(f"missing local recipes: {', '.join(sorted(missing))}", justfile)
            )
            continue
        distributions.append(Distribution(name=name, root=directory, justfile=justfile))
    return distributions, diagnostics


def _render(distributions: list[Distribution]) -> str:
    if not distributions:
        return "No workspace package distributions are registered yet."
    return "\n".join(
        f"{distribution.name:<40} {distribution.root.relative_to(ROOT)}"
        for distribution in distributions
    )


def _report(diagnostics: list[Diagnostic], root: Path) -> int:
    for diagnostic in diagnostics:
        print(diagnostic.render(root), file=sys.stderr)
    return 1 if diagnostics else 0


def list_distributions(root: Path = ROOT) -> int:
    distributions, diagnostics = discover(root)
    if _report(diagnostics, root):
        return 1
    print(_render(distributions))
    return 0


def doctor(root: Path = ROOT) -> int:
    distributions, diagnostics = discover(root)
    if _report(diagnostics, root):
        return 1
    if distributions:
        print(f"package workspace ready: {len(distributions)} distribution(s)")
    else:
        print("package workspace not created yet; no distributions to validate")
    return 0


def run(distribution_name: str, lane: str, arguments: list[str], root: Path = ROOT) -> int:
    distributions, diagnostics = discover(root)
    if _report(diagnostics, root):
        return 1
    distribution = next((item for item in distributions if item.name == distribution_name), None)
    if distribution is None:
        print(f"packages: unknown distribution {distribution_name!r}", file=sys.stderr)
        return 2
    completed = subprocess.run(
        [
            "just",
            "--justfile",
            str(distribution.justfile),
            "--working-directory",
            str(root),
            lane,
            *arguments,
        ],
        check=False,
    )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list")
    subcommands.add_parser("doctor")
    run_parser = subcommands.add_parser("run")
    run_parser.add_argument("distribution")
    run_parser.add_argument("lane", choices=("check", "test", "build"))
    run_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(argv)
    if parsed.command == "list":
        return list_distributions()
    if parsed.command == "doctor":
        return doctor()
    return run(parsed.distribution, parsed.lane, parsed.arguments)


if __name__ == "__main__":
    raise SystemExit(main())

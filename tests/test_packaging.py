"""The distribution is a contract too, and it is the one nobody runs locally.

Every failure here shows up only after an install: a module missing from the
wheel, a resource that was never packaged, a terminal renderer dragged into a
library dependency set. The tests read `pyproject.toml` as data and compare it
against the tree, so the packaging metadata cannot drift away from the code it
claims to describe.

`scripts/verify-wheel.sh` covers what static reading cannot — that the built
artifact actually installs and runs.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

SETUPTOOLS = PYPROJECT["tool"]["setuptools"]
PACKAGE_DIRS = {name: REPOSITORY_ROOT / path for name, path in SETUPTOOLS["package-dir"].items()}

#: Terminal rendering belongs to the CLI channel. A library that pulls Rich in
#: has quietly decided its embedder has a terminal.
CHANNEL_DEPENDENCIES = ("typer", "rich", "python-toon")


def _discovered_packages() -> set[str]:
    """Every importable package under the mapped roots, by distribution name."""
    found: set[str] = set()
    for distribution_name, root in PACKAGE_DIRS.items():
        for init in root.rglob("__init__.py"):
            relative = init.parent.relative_to(root).parts
            if any(part.startswith((".", "__")) for part in relative):
                continue
            found.add(".".join((distribution_name, *relative)))
    return found


def _requirement_names(requirements: list[str]) -> set[str]:
    """The distribution name of each PEP 508 requirement, without its markers."""
    return {re.split(r"[<>=!~;\[ @]", requirement, maxsplit=1)[0].strip() for requirement in requirements}


def test_the_declared_package_list_equals_what_is_actually_there() -> None:
    """A hand-maintained list is a list that silently goes stale.

    A package missing here imports fine from the checkout and `ModuleNotFound`s
    from the wheel, which is the worst possible place to find out.
    """
    assert set(SETUPTOOLS["packages"]) == _discovered_packages()


def test_both_distributed_packages_ship_a_py_typed_marker() -> None:
    """PEP 561: the marker sits in the top-level package and covers what is under it."""
    for distribution_name, root in PACKAGE_DIRS.items():
        assert (root / "py.typed").is_file(), distribution_name
        assert "py.typed" in SETUPTOOLS["package-data"][distribution_name], distribution_name


def test_the_library_half_does_not_depend_on_a_terminal() -> None:
    """`Xcron` is embeddable. An embedder gets no Typer, Rich, or TOON."""
    mandatory = _requirement_names(PYPROJECT["project"]["dependencies"])

    assert mandatory.isdisjoint(CHANNEL_DEPENDENCIES)
    assert mandatory == {"PyYAML", "jsonschema", "pydantic", "structlog", "xcfg"}


def test_the_console_script_declares_the_extra_it_needs() -> None:
    """`xcron` is a CLI entry point, so the renderers live in the `cli` extra."""
    extras = PYPROJECT["project"]["optional-dependencies"]

    assert _requirement_names(extras["cli"]) == set(CHANNEL_DEPENDENCIES)
    assert PYPROJECT["project"]["scripts"]["xcron"].startswith("xcron_cli.")
    assert "xcron[cli]" in PYPROJECT["dependency-groups"]["dev"]


def test_every_packaged_resource_pattern_matches_a_real_file() -> None:
    """A resource that ships nothing is a runtime failure waiting for an install."""
    for package, patterns in SETUPTOOLS["package-data"].items():
        distribution_name, _, relative = package.partition(".")
        directory = PACKAGE_DIRS[distribution_name].joinpath(*relative.split(".") if relative else [])

        assert directory.is_dir(), package
        for pattern in patterns:
            assert list(directory.glob(pattern)), (package, pattern)


def test_the_unpublished_dependency_travels_by_direct_reference() -> None:
    """`[tool.uv.sources]` is checkout-local and does not reach wheel metadata.

    xcfg is on no index, so a bare version specifier resolves against PyPI and
    fails for anyone installing the built artifact.
    """
    xcfg = next(
        requirement
        for requirement in PYPROJECT["project"]["dependencies"]
        if requirement.startswith("xcfg")
    )

    assert xcfg.startswith("xcfg @ git+")
    assert "@v" in xcfg.split("git+")[1], "the xcfg dependency must be pinned to a tag"
    assert "sources" not in PYPROJECT.get("tool", {}).get("uv", {})

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
#: Phase 8 collapsed two mapped roots into one. `package-dir` now maps the empty
#: prefix, so every declared package is a path under it.
SOURCE_ROOT = REPOSITORY_ROOT / SETUPTOOLS["package-dir"][""]

#: The public import root, and the two names it replaced.
DISTRIBUTED_PACKAGE = "xcron"
DEPRECATED_ROOTS = ("xcron_cli", "xcron_libs")

#: Terminal rendering belongs to the CLI channel. A library that pulls Rich in
#: has quietly decided its embedder has a terminal.
CHANNEL_DEPENDENCIES = ("typer", "rich", "python-toon")


def _discovered_packages() -> set[str]:
    """Every importable package under the source root, by dotted name."""
    found: set[str] = set()
    for init in SOURCE_ROOT.rglob("__init__.py"):
        relative = init.parent.relative_to(SOURCE_ROOT).parts
        if any(part.startswith((".", "__")) for part in relative):
            continue
        found.add(".".join(relative))
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


def test_the_marker_sits_in_the_one_package_that_covers_everything() -> None:
    """PEP 561: one marker in the top-level package types every subpackage.

    While the channel was its own distribution it needed its own marker. It is
    now `xcron.channels.cli`, so a second marker would be dead weight that
    future readers would take for a rule.
    """
    assert (SOURCE_ROOT / DISTRIBUTED_PACKAGE / "py.typed").is_file()
    assert "py.typed" in SETUPTOOLS["package-data"][DISTRIBUTED_PACKAGE]

    markers = {path.relative_to(SOURCE_ROOT) for path in SOURCE_ROOT.rglob("py.typed")}
    assert markers == {Path(DISTRIBUTED_PACKAGE) / "py.typed"}, sorted(map(str, markers))


def test_the_deprecated_roots_ship_but_hold_no_code() -> None:
    """The shims must install, or an old `import xcron_libs` fails outright.

    They must also stay empty: anything but the alias would be a second copy of
    behaviour, which is exactly what aliasing the module tree avoids.
    """
    for root in DEPRECATED_ROOTS:
        directory = SOURCE_ROOT / root
        assert root in SETUPTOOLS["packages"], root
        contents = sorted(path.name for path in directory.glob("*.py"))
        assert contents == ["__init__.py"], root


def test_first_party_code_imports_only_the_new_root() -> None:
    """The rename is not done while anything still reaches for the old names.

    Import Linter states the same rule over the module graph; this reads the
    text, so it also catches a string in a docstring example or a resource
    template that no import graph would ever traverse.
    """
    searched = (
        *(SOURCE_ROOT / DISTRIBUTED_PACKAGE).rglob("*.py"),
        *(REPOSITORY_ROOT / "tests").rglob("*.py"),
        *(REPOSITORY_ROOT / "resources").rglob("*"),
        *(REPOSITORY_ROOT / "scripts").rglob("*"),
    )
    #: The alias machinery has to name what it aliases, and so does this test.
    exempt = {
        SOURCE_ROOT / DISTRIBUTED_PACKAGE / "_deprecated_aliases.py",
        Path(__file__).resolve(),
        REPOSITORY_ROOT / "tests" / "test_deprecated_aliases.py",
        REPOSITORY_ROOT / "tests" / "architecture" / "test_layer_boundaries.py",
        # Its whole job is to install the wheel under both import roots and to
        # prove the deleted ones did not come back.
        REPOSITORY_ROOT / "scripts" / "verify-wheel.sh",
    }

    for path in searched:
        if not path.is_file() or path in exempt:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for old in (*DEPRECATED_ROOTS, "xcron_resources"):
            assert old not in text, (path.relative_to(REPOSITORY_ROOT), old)


def test_the_library_half_does_not_depend_on_a_terminal() -> None:
    """`Xcron` is embeddable. An embedder gets no Typer, Rich, or TOON."""
    mandatory = _requirement_names(PYPROJECT["project"]["dependencies"])

    assert mandatory.isdisjoint(CHANNEL_DEPENDENCIES)
    assert mandatory == {"PyYAML", "jsonschema", "pydantic", "structlog", "xcfg"}


def test_the_console_script_declares_the_extra_it_needs() -> None:
    """`xcron` is a CLI entry point, so the renderers live in the `cli` extra."""
    extras = PYPROJECT["project"]["optional-dependencies"]

    assert _requirement_names(extras["cli"]) == set(CHANNEL_DEPENDENCIES)
    assert PYPROJECT["project"]["scripts"]["xcron"].startswith("xcron.channels.cli.")
    assert "xcron[cli]" in PYPROJECT["dependency-groups"]["dev"]


def test_every_packaged_resource_pattern_matches_a_real_file() -> None:
    """A resource that ships nothing is a runtime failure waiting for an install."""
    for package, patterns in SETUPTOOLS["package-data"].items():
        directory = SOURCE_ROOT.joinpath(*package.split("."))

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

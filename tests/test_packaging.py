"""Distribution metadata is part of the public capability contract."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
DEFAULT_PROVIDERS = {
    "xcron-capability-workspace-local",
    "xcron-capability-settings-xcfg",
    "xcron-capability-observability-structlog",
    "xcron-capability-manifest-yaml",
    "xcron-capability-scheduler-native",
    "xcron-capability-jobs-manifest",
    "xcron-capability-logs-local",
    "xcron-capability-metrics-local",
    "xcron-capability-agent-hooks-local",
}
TERMINAL_DEPENDENCIES = {"typer", "rich", "python-toon", "toon", "click"}


def _requirement_names(requirements: list[str]) -> set[str]:
    return {re.split(r"[<>=!~;\[ @]", item, maxsplit=1)[0].strip() for item in requirements}


def test_root_distribution_is_a_metadata_only_default_aggregate() -> None:
    setuptools = PYPROJECT["tool"]["setuptools"]
    dependencies = _requirement_names(PYPROJECT["project"]["dependencies"])

    assert setuptools["packages"] == []
    assert not (REPOSITORY_ROOT / "src" / "xcron").exists()
    assert dependencies == {"xcron-sdk", *DEFAULT_PROVIDERS}
    assert dependencies.isdisjoint(TERMINAL_DEPENDENCIES)
    assert "scripts" not in PYPROJECT["project"]


def test_cli_is_an_explicit_aggregate_extra() -> None:
    extras = PYPROJECT["project"]["optional-dependencies"]

    assert _requirement_names(extras["cli"]) == {"xcron-cli"}
    assert "xcron[cli]" in PYPROJECT["dependency-groups"]["dev"]


def test_workspace_sources_name_every_distributed_runtime_member() -> None:
    sources = PYPROJECT["tool"]["uv"]["sources"]
    dependencies = _requirement_names(PYPROJECT["project"]["dependencies"])

    assert dependencies <= set(sources)
    assert {"xcron-kernel", "xcron-contracts", "xcron-sdk", "xcron-cli", "xcron-testing"} <= set(sources)
    assert "xcron-capability-metrics-test" not in sources


def test_every_runtime_distribution_has_its_own_descriptor_docs_and_justfile() -> None:
    distributions = [
        *sorted((REPOSITORY_ROOT / "packages").glob("xcron-*/pyproject.toml")),
        *sorted((REPOSITORY_ROOT / "capabilities").glob("xcron-capability-*/pyproject.toml")),
    ]

    assert distributions
    for metadata in distributions:
        package_root = metadata.parent
        assert (package_root / "README.md").is_file(), package_root
        assert (package_root / "justfile").is_file(), package_root
        package = tomllib.loads(metadata.read_text(encoding="utf-8"))
        assert package["project"]["name"].startswith("xcron"), package_root


def test_settings_provider_carries_its_unpublished_dependency() -> None:
    settings = tomllib.loads(
        (REPOSITORY_ROOT / "capabilities/xcron-capability-settings-xcfg/pyproject.toml").read_text(encoding="utf-8")
    )
    xcfg = next(item for item in settings["project"]["dependencies"] if item.startswith("xcfg"))

    assert xcfg.startswith("xcfg @ git+")
    assert "@v" in xcfg.split("git+")[1]
    assert "xcfg" not in settings.get("tool", {}).get("uv", {}).get("sources", {})

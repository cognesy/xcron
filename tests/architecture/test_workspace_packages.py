"""Structural contracts for independently buildable xcron distributions.

The product shares the ``xcron`` namespace, but no wheel is a hidden bridge.
These checks deliberately inspect the workspace instead of importing it: a
provider must remain valid when built and installed independently.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from xcron.testing import check_package_boundaries, source_roots


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPOSITORY_ROOT / "packages"
CAPABILITY_ROOT = REPOSITORY_ROOT / "capabilities"
CLI_ROOT = PACKAGE_ROOT / "xcron-cli" / "src" / "xcron_cli"
KERNEL_ROOT = PACKAGE_ROOT / "xcron-kernel" / "src" / "xcron" / "kernel"
CONTRACTS_ROOT = PACKAGE_ROOT / "xcron-contracts" / "src" / "xcron" / "contracts"
SDK_ROOT = PACKAGE_ROOT / "xcron-sdk" / "src" / "xcron" / "sdk"
PROVIDER_DISTRIBUTIONS = tuple(sorted(CAPABILITY_ROOT.glob("xcron-capability-*")))
TERMINAL_IMPORTS = ("typer", "rich", "toon", "click")
ENVIRONMENT_READERS = {
    "capabilities/xcron-capability-scheduler-native/src/xcron/capabilities/scheduler_native/wrapper.py",
    "capabilities/xcron-capability-settings-xcfg/src/xcron/capabilities/settings_xcfg/provider.py",
    "capabilities/xcron-capability-workspace-local/src/xcron/capabilities/workspace_local/provider.py",
    "capabilities/xcron-capability-workspace-local/src/xcron/capabilities/workspace_local/resolver.py",
}


def _files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _metadata(distribution: Path) -> dict[str, object]:
    return tomllib.loads((distribution / "pyproject.toml").read_text(encoding="utf-8"))


def test_workspace_has_no_legacy_source_tree_or_import_bridge() -> None:
    assert not (REPOSITORY_ROOT / "src" / "xcron").exists()

    production = [path for root in source_roots(REPOSITORY_ROOT) for path in _files(root)]
    legacy = ("xcron.channels", "xcron.runtime", "xcron.configuration", "xcron.domain", "xcron.shared")
    offenders = {
        path.relative_to(REPOSITORY_ROOT): sorted(
            name for name in _imports(path) if name == legacy or name.startswith(legacy)
        )
        for path in production
    }
    assert not {path: names for path, names in offenders.items() if names}


def test_every_runtime_distribution_is_a_self_contained_namespace_package() -> None:
    distributions = [*sorted(PACKAGE_ROOT.glob("xcron-*")), *PROVIDER_DISTRIBUTIONS]

    assert distributions
    for distribution in distributions:
        metadata = _metadata(distribution)
        assert (distribution / "README.md").is_file(), distribution
        assert (distribution / "justfile").is_file(), distribution
        assert (distribution / "capability.toml").is_file(), distribution
        assert metadata["project"]["name"].startswith("xcron")
        if distribution.name == "xcron-cli":
            assert (distribution / "src/xcron_cli/__init__.py").is_file(), distribution
            continue
        source = distribution / "src" / "xcron"
        assert source.is_dir(), distribution
        assert not (source / "__init__.py").exists(), distribution
        capabilities = source / "capabilities"
        if capabilities.exists():
            assert not (capabilities / "__init__.py").exists(), distribution


def test_provider_metadata_declares_one_discoverable_capability_and_owns_its_assets() -> None:
    for distribution in PROVIDER_DISTRIBUTIONS:
        metadata = _metadata(distribution)
        descriptor = tomllib.loads((distribution / "capability.toml").read_text(encoding="utf-8"))
        entry_points = metadata["project"].get("entry-points", {})
        declared = entry_points.get("xcron.capabilities", {})
        assert len(declared) == 1, distribution
        entry_point = next(iter(declared.values()))
        module, _, attribute = entry_point.partition(":")
        assert attribute == "CAPABILITY", (distribution, entry_point)
        module_path = distribution / "src" / Path(*module.split("."))
        assert (module_path.with_suffix(".py")).is_file() or module_path.is_dir(), entry_point
        package = descriptor["package"]
        provider = descriptor["provider"]
        assert package["kind"] == "provider"
        assert package["namespace"] == module.removesuffix(".provider")
        assert provider["entry_point"] == entry_point
        assert provider["ports"]
        for asset in provider["assets"]:
            assert (module_path.parent / asset).is_file(), (distribution, asset)
        assert (distribution / "tests").is_dir(), distribution
        assert (distribution / "README.md").read_text(encoding="utf-8").strip(), distribution


def test_kernel_contracts_sdk_and_cli_keep_their_separate_responsibilities() -> None:
    for path in _files(KERNEL_ROOT):
        assert not any(name.startswith("xcron.capabilities") for name in _imports(path)), path

    for path in _files(CONTRACTS_ROOT):
        imports = _imports(path)
        assert not any(name.startswith(("xcron.capabilities", "xcron_cli")) for name in imports), path
        assert not any(name.startswith(TERMINAL_IMPORTS) for name in imports), path

    for path in _files(SDK_ROOT):
        imports = _imports(path)
        assert not any(name.startswith(("xcron.capabilities", "xcron_cli", *TERMINAL_IMPORTS)) for name in imports), path

    typer_imports = _imports(CLI_ROOT / "typer_app.py")
    assert "xcron.sdk" in typer_imports
    assert not any(name.startswith("xcron.capabilities") for name in typer_imports)


def test_providers_are_peer_independent_and_channel_free() -> None:
    violations = check_package_boundaries(REPOSITORY_ROOT)
    assert not violations, violations

    for distribution in PROVIDER_DISTRIBUTIONS:
        for path in _files(distribution / "src" / "xcron"):
            imports = _imports(path)
            assert not any(name.startswith(("xcron_cli", *TERMINAL_IMPORTS)) for name in imports), path


def test_environment_reads_are_explicit_and_provider_owned() -> None:
    readers = {
        str(path.relative_to(REPOSITORY_ROOT))
        for root in source_roots(REPOSITORY_ROOT)
        for path in _files(root)
        if "os.environ" in (source := path.read_text(encoding="utf-8")) or "os.getenv" in source
    }

    assert readers == ENVIRONMENT_READERS


def test_channel_and_provider_resources_live_with_their_readers() -> None:
    assert (CLI_ROOT / "resources/help/root.md").is_file()
    assert (
        CAPABILITY_ROOT
        / "xcron-capability-manifest-yaml/src/xcron/capabilities/manifest_yaml/resources/schemas/schedules.schema.yaml"
    ).is_file()
    assert (
        CAPABILITY_ROOT
        / "xcron-capability-observability-structlog/src/xcron/capabilities/observability_structlog/resources/logging/default.yaml"
    ).is_file()
    assert not (REPOSITORY_ROOT / "resources" / "schemas").exists()
    assert not (REPOSITORY_ROOT / "resources" / "logging").exists()


def test_ops_catalogue_names_the_extracted_cli_assets() -> None:
    for path in (REPOSITORY_ROOT / "ops/cli/capability.yaml", REPOSITORY_ROOT / "ops/skills/capability.yaml"):
        source = path.read_text(encoding="utf-8")
        assert "packages/xcron-cli/src/xcron_cli/resources/help/**" in source or path.name == "capability.yaml" and "ops/cli" in str(path)
    assert "packages/xcron-cli/src/xcron_cli/**" in (
        REPOSITORY_ROOT / "ops/cli/capability.yaml"
    ).read_text(encoding="utf-8")

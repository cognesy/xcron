"""The leaves stay leaves and the channel stays a channel.

`libs/domain` and `libs/shared` may be imported by anything and may import
almost nothing; that asymmetry is what makes them safe to depend on. `apps/cli`
sits at the other end: it may reach the SDK and nothing below it, and nothing
below it may reach back.
"""

from __future__ import annotations

import pytest

from tests.architecture.scanner import (
    REPOSITORY_ROOT,
    imports_anything_matching,
    source_files,
)

CHANNEL_AND_ABOVE = ("xcron_cli", "xcron_libs.sdk", "xcron_libs.runtime")
RENDERERS = ("typer", "rich", "toon")


def test_domain_is_a_leaf() -> None:
    """`libs/domain` holds manifest value types; diffing belongs to a module."""
    forbidden = (*CHANNEL_AND_ABOVE, *RENDERERS, "xcron_libs.capabilities")
    paths = source_files("libs/domain")

    assert paths, "libs/domain must not be empty"
    for path in paths:
        assert not imports_anything_matching(path, forbidden), path


def test_shared_is_a_strict_leaf() -> None:
    """The moment it can import a capability it stops being a leaf.

    It becomes a second, undeclared coupling point instead: something every
    module already depends on, now with opinions of its own.
    """
    forbidden = (*CHANNEL_AND_ABOVE, *RENDERERS, "xcron_libs.capabilities")
    paths = tuple(path for path in source_files("libs/shared") if path.name != "__init__.py")

    assert paths, "libs/shared must not be empty"
    for path in paths:
        assert not imports_anything_matching(path, forbidden), path


def test_capabilities_do_not_depend_on_the_cli_or_rendering_boundary() -> None:
    for path in source_files("libs/capabilities"):
        assert not imports_anything_matching(path, ("xcron_cli", *RENDERERS)), path


def test_runtime_is_composition_only_and_channel_independent() -> None:
    """The composition root builds the object graph; it is not built by it."""
    for path in source_files("libs/runtime"):
        assert not imports_anything_matching(path, ("xcron_cli", "xcron_libs.sdk")), path


def test_no_library_module_imports_the_cli_channel() -> None:
    """`xcron_cli` owns its projections; `libs/` may never reach back into it."""
    for path in source_files("libs"):
        offenders = imports_anything_matching(path, ("xcron_cli",))
        assert not offenders, (path.relative_to(REPOSITORY_ROOT), offenders)


def test_the_typer_shell_reaches_the_sdk_and_nothing_below_it() -> None:
    from tests.architecture.scanner import imported_modules

    imported = imported_modules(REPOSITORY_ROOT / "apps" / "cli" / "typer_app.py")

    assert "xcron_libs" in imported
    assert not any(name.startswith("xcron_libs.capabilities") for name in imported)


def test_the_cli_projection_cluster_lives_in_the_channel_that_owns_it() -> None:
    """Projection is a channel decision: what a result looks like to a terminal."""
    cli_root = REPOSITORY_ROOT / "apps" / "cli"
    for relative in (
        "contracts.py",
        "responses.py",
        "mappers.py",
        "presenters/axi_presenter.py",
        "presenters/toon_renderer.py",
        "presenters/tmux_renderer.py",
        "presenters/help_renderer.py",
        "resources/help/root.md",
    ):
        assert (cli_root / relative).is_file(), relative


def test_every_packaged_resource_lives_inside_the_module_that_reads_it() -> None:
    """A resource directory is owned state; it ships with its one reader."""
    from xcron_libs.capabilities.manifest.contracts import SCHEMA_PACKAGE
    from xcron_libs.shared.logging_config import LOGGING_PACKAGE

    assert SCHEMA_PACKAGE == "xcron_libs.capabilities.manifest.resources.schemas"
    assert LOGGING_PACKAGE == "xcron_libs.shared.resources.logging"

    assert (
        REPOSITORY_ROOT / "libs/capabilities/manifest/resources/schemas/schedules.schema.yaml"
    ).is_file()
    assert (REPOSITORY_ROOT / "libs/shared/resources/logging/default.yaml").is_file()
    assert not (REPOSITORY_ROOT / "resources" / "schemas").exists()
    assert not (REPOSITORY_ROOT / "resources" / "logging").exists()


@pytest.mark.parametrize(
    ("directory", "reason"),
    [
        ("libs/services", "21 modules and no owner"),
        ("libs/infra", "dead by Phase 4"),
        ("libs/actions", "a time-boxed compatibility facade"),
        ("libs/capabilities/home", "folded into workspace"),
        ("resources/schemas", "moved inside the manifest module"),
    ],
)
def test_the_ownerless_directories_stay_deleted(directory: str, reason: str) -> None:
    """Each of these was a place to put a file that belonged to nobody.

    A recreated directory is the same failure returning, so the check is on the
    path rather than on any particular import.
    """
    assert not (REPOSITORY_ROOT / directory).exists(), reason


def test_nothing_imports_a_deleted_package() -> None:
    deleted = (
        "xcron_libs.actions",
        "xcron_libs.services",
        "xcron_libs.infra",
        "xcron_resources",
    )
    for path in source_files("libs", "apps"):
        offenders = imports_anything_matching(path, deleted)
        assert not offenders, (path.relative_to(REPOSITORY_ROOT), offenders)

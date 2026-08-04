"""The leaves stay leaves and the channel stays a channel.

`xcron.domain` and `xcron.shared` may be imported by anything and may import
almost nothing; that asymmetry is what makes them safe to depend on. `xcron.channels.cli`
sits at the other end: it may reach the SDK and nothing below it, and nothing
below it may reach back.
"""

from __future__ import annotations

import pytest

from tests.architecture.scanner import (
    CHANNEL_ROOT,
    REPOSITORY_ROOT,
    SOURCE_ROOT,
    imports_anything_matching,
    source_files,
)

#: `xcron.channels` is inside the distributed package now, so "the library half"
#: is no longer "a different directory" — it is everything under `src/xcron`
#: that is not a channel. The boundary is the same one; only the way to name it
#: changed.
CHANNELS_ROOT = SOURCE_ROOT / "channels"

CHANNEL_AND_ABOVE = ("xcron.channels.cli", "xcron.sdk", "xcron.runtime")
RENDERERS = ("typer", "rich", "toon")


def test_domain_is_a_leaf() -> None:
    """`xcron.domain` holds manifest value types; diffing belongs to a module."""
    forbidden = (*CHANNEL_AND_ABOVE, *RENDERERS, "xcron.capabilities")
    paths = source_files("src/xcron/domain")

    assert paths, "xcron.domain must not be empty"
    for path in paths:
        assert not imports_anything_matching(path, forbidden), path


def test_shared_is_a_strict_leaf() -> None:
    """The moment it can import a capability it stops being a leaf.

    It becomes a second, undeclared coupling point instead: something every
    module already depends on, now with opinions of its own.
    """
    forbidden = (*CHANNEL_AND_ABOVE, *RENDERERS, "xcron.capabilities")
    paths = tuple(path for path in source_files("src/xcron/shared") if path.name != "__init__.py")

    assert paths, "xcron.shared must not be empty"
    for path in paths:
        assert not imports_anything_matching(path, forbidden), path


def test_capabilities_do_not_depend_on_the_cli_or_rendering_boundary() -> None:
    for path in source_files("src/xcron/capabilities"):
        assert not imports_anything_matching(path, ("xcron.channels.cli", *RENDERERS)), path


def test_runtime_is_composition_only_and_channel_independent() -> None:
    """The composition root builds the object graph; it is not built by it."""
    for path in source_files("src/xcron/runtime"):
        assert not imports_anything_matching(path, ("xcron.channels.cli", "xcron.sdk")), path


def test_no_library_module_imports_the_cli_channel() -> None:
    """The channel owns its projections; nothing below it may reach back in."""
    library_files = [
        path for path in source_files("src/xcron") if not path.is_relative_to(CHANNELS_ROOT)
    ]

    assert library_files, "the library half disappeared; update this contract"
    for path in library_files:
        offenders = imports_anything_matching(path, ("xcron.channels",))
        assert not offenders, (path.relative_to(REPOSITORY_ROOT), offenders)


def test_the_typer_shell_reaches_the_sdk_and_nothing_below_it() -> None:
    from tests.architecture.scanner import imported_modules

    imported = imported_modules(CHANNEL_ROOT / "typer_app.py")

    assert "xcron" in imported
    assert not any(name.startswith("xcron.capabilities") for name in imported)


def test_the_cli_projection_cluster_lives_in_the_channel_that_owns_it() -> None:
    """Projection is a channel decision: what a result looks like to a terminal."""
    cli_root = CHANNEL_ROOT
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
    from xcron.capabilities.manifest.contracts import SCHEMA_PACKAGE
    from xcron.shared.logging_config import LOGGING_PACKAGE

    assert SCHEMA_PACKAGE == "xcron.capabilities.manifest.resources.schemas"
    assert LOGGING_PACKAGE == "xcron.shared.resources.logging"

    assert (
        SOURCE_ROOT / "capabilities/manifest/resources/schemas/schedules.schema.yaml"
    ).is_file()
    assert (SOURCE_ROOT / "shared/resources/logging/default.yaml").is_file()
    assert not (REPOSITORY_ROOT / "resources" / "schemas").exists()
    assert not (REPOSITORY_ROOT / "resources" / "logging").exists()


@pytest.mark.parametrize(
    ("directory", "reason"),
    [
        ("src/xcron/services", "21 modules and no owner"),
        ("src/xcron/infra", "dead by Phase 4"),
        ("src/xcron/actions", "a time-boxed compatibility facade"),
        ("src/xcron/capabilities/home", "folded into workspace"),
        ("resources/schemas", "moved inside the manifest module"),
        ("src/xcron_libs", "a one-release alias for xcron, now expired"),
        ("src/xcron_cli", "a one-release alias for xcron.channels.cli, now expired"),
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
        "xcron.actions",
        "xcron.services",
        "xcron.infra",
        "xcron_resources",
        "xcron_libs",
        "xcron_cli",
    )
    for path in source_files("src/xcron"):
        offenders = imports_anything_matching(path, deleted)
        assert not offenders, (path.relative_to(REPOSITORY_ROOT), offenders)

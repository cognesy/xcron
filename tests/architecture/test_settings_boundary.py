"""Settings are resolved once, and a second reader is free to disagree.

The dependency direction is checkable by an import graph, and Import Linter
checks it. What only a source scan can say is *which files name `os.environ`* —
a file can read the environment without importing anything interesting, and
that is precisely the drift these tests exist to catch.
"""

from __future__ import annotations

from tests.architecture.scanner import REPOSITORY_ROOT, imported_modules, source_files

CONFIGURATION_MODULES = source_files("libs/configuration")

#: Files allowed to name `os.environ` or `os.getenv`. Everything else receives
#: settings as values from the composition root.
DECLARED_ENVIRONMENT_READERS = {
    # Composes settings from the published `XCRON_*` variables.
    "libs/configuration/loader.py",
    # Workspace identity selects *which* config files are read, so it cannot
    # itself come from one.
    "libs/capabilities/workspace/resolver.py",
    # Passes the environment it was handed down to the two above.
    "libs/runtime/composition.py",
    # Logging bootstraps before a runtime exists; see the Phase 5 record.
    "libs/shared/logging_config.py",
    # Emitted into generated wrapper scripts as text, not read in this process.
    "libs/capabilities/reconciliation/wrapper.py",
}


def test_only_declared_modules_read_the_environment() -> None:
    """Adding a file here is an architectural decision, not a fix.

    It means code below the composition root now has its own opinion about the
    environment, and two opinions is exactly the bug Phase 5 removed.
    """
    readers = {
        str(path.relative_to(REPOSITORY_ROOT))
        for path in source_files("libs", "apps")
        if "os.environ" in (source := path.read_text(encoding="utf-8")) or "os.getenv" in source
    }

    assert readers == DECLARED_ENVIRONMENT_READERS


def test_the_configuration_library_has_exactly_one_importer_of_xcfg() -> None:
    """`xcfg` is a mechanism, reached through xcron's own surface or not at all."""
    importers = {
        str(path.relative_to(REPOSITORY_ROOT))
        for path in source_files("libs", "apps", "tests")
        if any(name == "xcfg" or name.startswith("xcfg.") for name in imported_modules(path))
    }

    assert importers == {"libs/configuration/loader.py"}


def test_configuration_is_a_leaf_that_no_capability_depends_on() -> None:
    """A capability importing the loader would resolve configuration a second
    time, at a different moment, from a different environment."""
    forbidden = (
        "xcron_cli",
        "xcron_libs.capabilities",
        "xcron_libs.runtime",
        "xcron_libs.sdk",
    )
    assert CONFIGURATION_MODULES, "libs/configuration must not be empty"
    for path in CONFIGURATION_MODULES:
        assert not any(name.startswith(forbidden) for name in imported_modules(path)), path

    for path in source_files("libs/capabilities"):
        offenders = sorted(
            name
            for name in imported_modules(path)
            if name.startswith("xcron_libs.configuration")
        )
        assert not offenders, (path.relative_to(REPOSITORY_ROOT), offenders)


def test_the_composition_root_is_the_only_place_settings_are_loaded() -> None:
    loaders = {
        str(path.relative_to(REPOSITORY_ROOT))
        for path in source_files("libs", "apps")
        if "xcron_libs.configuration.api" in imported_modules(path)
    }

    assert loaders == {"libs/runtime/composition.py"}


def test_the_workspace_module_owns_what_identity_means() -> None:
    """`XCRON_HOME` and `XCRON_PROJECT` choose which config files are read, so
    they are not settings and cannot be composed from one."""
    from xcron_libs.capabilities.workspace.api import XCRON_PROJECT_ENV_VAR
    from xcron_libs.configuration.contracts import ENV_SETTINGS

    assert XCRON_PROJECT_ENV_VAR not in ENV_SETTINGS
    assert "XCRON_HOME" not in ENV_SETTINGS

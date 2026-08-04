"""The old import roots keep working for one release, and say so out loud.

Phase 8 moved the public root from `xcron_libs`/`xcron_cli` to `xcron`. Anyone
who had imported the old names — a script, a hook, another repository — should
not have to change on the same day. The shims buy that time, and the warning is
what stops the reprieve from becoming permanent.

The important claim is *identity*, not equality: an aliased module is the real
module object. A shim that re-imported the source would give a caller a second
copy of module-level state, and `monkeypatch.setattr` on one name would not be
seen through the other.
"""

from __future__ import annotations

import importlib
import sys

import pytest

from xcron._deprecated_aliases import ALIASES

#: Old dotted name -> the module it must resolve to.
ALIASED_MODULES = (
    ("xcron_libs.sdk.client", "xcron.sdk.client"),
    ("xcron_libs.capabilities.jobs.api", "xcron.capabilities.jobs.api"),
    ("xcron_libs.domain.models", "xcron.domain.models"),
    ("xcron_cli.typer_app", "xcron.channels.cli.typer_app"),
    ("xcron_cli.presenters.toon_renderer", "xcron.channels.cli.presenters.toon_renderer"),
)


@pytest.mark.parametrize(("old", "new"), ALIASED_MODULES)
def test_an_old_name_resolves_to_the_same_module_object(old: str, new: str) -> None:
    assert importlib.import_module(old) is importlib.import_module(new)


def test_the_alias_table_covers_both_retired_roots() -> None:
    assert ALIASES == {"xcron_libs": "xcron", "xcron_cli": "xcron.channels.cli"}


@pytest.mark.parametrize("root", sorted(ALIASES))
def test_importing_a_retired_root_warns(root: str) -> None:
    """Purge first: the warning fires on execution, and a cached module ran already."""
    for name in [name for name in sys.modules if name == root or name.startswith(f"{root}.")]:
        del sys.modules[name]

    with pytest.warns(DeprecationWarning, match=f"{root} is a deprecated alias"):
        importlib.import_module(root)


def test_the_library_root_still_re_exports_the_sdk_surface() -> None:
    """`from xcron_libs import Xcron` is the shape most callers actually used."""
    import xcron
    import xcron_libs

    assert xcron_libs.Xcron is xcron.Xcron
    assert set(xcron_libs.__all__) == set(xcron.__all__)


def test_state_is_shared_across_the_two_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """The point of aliasing rather than copying, stated as a test."""
    new = importlib.import_module("xcron.sdk.client")
    old = importlib.import_module("xcron_libs.sdk.client")

    monkeypatch.setattr(new, "_alias_probe", object(), raising=False)
    assert old._alias_probe is new._alias_probe

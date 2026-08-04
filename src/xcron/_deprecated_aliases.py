"""The one-release import shim for `xcron_libs` and `xcron_cli`.

A `__init__.py` that re-exports names is not enough: callers write
`from xcron_libs.capabilities.jobs.api import list_jobs`, and Python resolves
that submodule through the import system, not through the parent's namespace.
So this installs a meta-path finder that maps the old prefix onto the new one
and hands back the *same module object*. Aliasing rather than copying is what
keeps `isinstance`, module-level state, and `monkeypatch.setattr` working
across the two names.

Deleting this file is the whole of the removal: nothing else imports it.
"""

from __future__ import annotations

import importlib
import sys
import warnings
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType

#: Old prefix -> the package it now lives under.
ALIASES = {
    "xcron_libs": "xcron",
    "xcron_cli": "xcron.channels.cli",
}

DEPRECATION_MESSAGE = (
    "{old} is a deprecated alias for {new} and will be removed in the next "
    "release; import {new} instead"
)


class _AliasLoader(Loader):
    def __init__(self, target: str) -> None:
        self._target = target

    def create_module(self, spec: ModuleSpec) -> ModuleType:
        return importlib.import_module(self._target)

    def exec_module(self, module: ModuleType) -> None:
        """Already executed under its real name; aliasing must not re-run it."""


class _AliasFinder(MetaPathFinder):
    """Resolves `xcron_libs.sdk.client` to the module object `xcron.sdk.client`.

    Only submodules, never the roots: `src/xcron_libs/__init__.py` is a real
    file, and letting it run is what emits the warning. Aliasing the root too
    would silence the warning whenever the *other* root was imported first.
    """

    def find_spec(self, fullname: str, path: object = None, target: object = None):
        for old, new in ALIASES.items():
            if fullname.startswith(f"{old}."):
                return ModuleSpec(fullname, _AliasLoader(new + fullname[len(old) :]))
        return None


def install_aliases(requested_by: str) -> None:
    """Warn once for the alias root that was imported, and register the finder."""
    warnings.warn(
        DEPRECATION_MESSAGE.format(old=requested_by, new=ALIASES[requested_by]),
        DeprecationWarning,
        stacklevel=3,
    )
    if not any(isinstance(finder, _AliasFinder) for finder in sys.meta_path):
        # Ahead of PathFinder, not after it. The alias root's `__path__` leads
        # back to the real directory, so PathFinder would happily load a second
        # copy of `client.py` under the old name — two module objects for one
        # file, which is the exact failure aliasing exists to prevent.
        sys.meta_path.insert(0, _AliasFinder())

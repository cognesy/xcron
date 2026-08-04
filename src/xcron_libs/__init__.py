"""Deprecated alias for the `xcron` package. Removed after one release.

`xcron_libs` and `xcron_cli` named the repository's directories — `libs/` and
`apps/` — which made the layout the public API. Moving a file was therefore a
breaking change for anyone importing it. The product package is `xcron`.

This module aliases the whole tree rather than re-exporting a handful of names,
because callers import submodules (`xcron_libs.capabilities.jobs.api`), not just
the root. Every aliased module *is* the real module — `xcron_libs.sdk.client is
xcron.sdk.client` — so isinstance checks, singletons, and monkeypatching all
behave as if the old name had never existed.
"""

from __future__ import annotations

from xcron import (
    ClientClosedError,
    HookError,
    UnknownBackendError,
    Xcron,
    XcronError,
    XcronOptions,
)
from xcron._deprecated_aliases import install_aliases

__all__ = [
    "ClientClosedError",
    "HookError",
    "UnknownBackendError",
    "Xcron",
    "XcronError",
    "XcronOptions",
]

install_aliases(__name__)

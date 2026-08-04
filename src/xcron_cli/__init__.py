"""Deprecated alias for `xcron.channels.cli`. Removed after one release.

See `xcron._deprecated_aliases` for why this aliases the module tree instead of
re-exporting names.
"""

from __future__ import annotations

from xcron._deprecated_aliases import install_aliases

__all__: list[str] = []

install_aliases(__name__)

"""TOON rendering helpers for xcron CLI output.

This module is the only place in xcron that should talk directly to the
third-party ``python-toon`` package. Keeping the dependency behind this adapter
lets the CLI presentation layer own schema shaping while preserving an easy
escape hatch if the upstream library changes or is replaced later.

One current upstream quirk is that tabular array headers include the explicit
default delimiter in the length marker, for example ``items[2,]{id}:``. xcron
accepts that upstream behavior for now rather than rewriting the encoder output.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from toon import encode


TOON_OPTIONS = {
    "indent": 2,
    "delimiter": ",",
}


def normalize_for_toon(value: Any) -> Any:
    """Normalize common xcron values into TOON-friendly containers.

    Command/presenter code should shape the payload schema before calling this
    function. The renderer only normalizes Python container types so the output
    boundary stays deterministic and isolated from third-party behavior.
    """

    if isinstance(value, Mapping):
        return {str(key): normalize_for_toon(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [normalize_for_toon(item) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_for_toon(item) for item in value]
    return value


def render_toon(value: Any) -> str:
    """Render one normalized payload to TOON text."""

    return encode(normalize_for_toon(value), options=TOON_OPTIONS)


__all__ = ["normalize_for_toon", "render_toon", "TOON_OPTIONS"]

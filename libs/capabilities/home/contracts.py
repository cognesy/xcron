"""Public contracts owned by the xcron home-initialization module.

This module is one of the two entry points outside code may import; the other
is :mod:`xcron_libs.capabilities.home.api`.

Nothing here depends on a channel, renderer, or CLI response type.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InitHomeResult:
    """Structured result for the init use case."""

    xcron_home: str
    schedules_dir: str
    manifest_path: str
    created: bool

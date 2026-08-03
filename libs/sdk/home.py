"""Typed xcron-home initialization API."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from xcron_libs.capabilities.home.api import init_home
from xcron_libs.capabilities.home.contracts import InitHomeResult


class HomeAPI:
    """Initialize the default xcron home without a CLI dependency."""

    def __init__(self, guard: Callable[[], None]) -> None:
        self._guard = guard

    def initialize(
        self, *, xcron_home: str | Path | None = None
    ) -> InitHomeResult:
        self._guard()
        return init_home(
            xcron_home=Path(xcron_home).expanduser().resolve()
            if xcron_home is not None
            else None
        )

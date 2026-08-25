"""Channel contribution declarations; adapters remain outside provider core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class CliAdapter(Protocol):
    """A channel-owned adapter contribution that may use terminal libraries."""

    def register(self, application: object) -> None:
        """Register one command path on the supplied channel application."""


@dataclass(frozen=True, slots=True)
class CliContribution:
    """One declared CLI command path owned by a selected capability provider."""

    command_path: tuple[str, ...]
    capability: str
    implementation: str
    help_key: str
    factory: Callable[[], CliAdapter]

    def __post_init__(self) -> None:
        if not self.command_path or any(not part for part in self.command_path):
            raise ValueError("CLI command paths must contain one or more non-empty parts")

"""Small, provider-independent checks for runtime-checkable xcron ports."""

from __future__ import annotations

from typing import Protocol


class PortConformanceError(TypeError):
    """A provider registration exposes a port with the wrong public shape."""


def assert_port(value: object, port: type[Protocol]) -> None:
    """Require a provider value to satisfy a runtime-checkable port protocol.

    ``Protocol`` signature checking is intentionally a static concern. This
    runtime check proves that all required public members exist before a host
    routes a call to an installed provider.
    """
    if not getattr(port, "_is_runtime_protocol", False):
        raise TypeError(f"{port.__name__} must be decorated with @runtime_checkable")
    if not isinstance(value, port):
        raise PortConformanceError(
            f"{type(value).__name__} does not implement the {port.__name__} contract"
        )

"""Stable errors raised by the public xcron SDK."""


class XcronError(Exception):
    """Base class for SDK-specific failures."""


class ClientClosedError(XcronError):
    """Raised when an API is used after its owning client is closed."""

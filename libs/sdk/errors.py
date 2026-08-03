"""Stable errors raised by the public xcron SDK."""


class XcronError(Exception):
    """Base class for SDK-specific failures."""


class ClientClosedError(XcronError):
    """Raised when an API is used after its owning client is closed."""


class UnknownBackendError(XcronError):
    """Raised when the selected scheduler backend is not registered."""


class HookError(XcronError):
    """Raised when the agent-hooks capability cannot complete an operation."""

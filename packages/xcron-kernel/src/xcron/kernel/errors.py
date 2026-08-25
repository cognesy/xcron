"""Stable, product-neutral failures from capability composition."""

from __future__ import annotations


class CapabilityError(RuntimeError):
    """Base error carrying a machine-stable code and a concrete remedy."""

    code = "capability_error"

    def __init__(self, message: str, remedy: str) -> None:
        super().__init__(message)
        self.message = message
        self.remedy = remedy


class CapabilityUnavailableError(CapabilityError):
    code = "capability_unavailable"


class CapabilityAmbiguousError(CapabilityError):
    code = "capability_ambiguous"


class CapabilityIncompatibleError(CapabilityError):
    code = "capability_incompatible"


class CapabilityCycleError(CapabilityError):
    code = "capability_cycle"


class CapabilityCollisionError(CapabilityError):
    code = "capability_collision"


class CapabilityMalformedError(CapabilityError):
    code = "capability_malformed"


class CapabilityClosedError(CapabilityError):
    code = "capability_closed"

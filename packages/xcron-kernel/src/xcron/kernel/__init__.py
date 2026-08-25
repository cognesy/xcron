"""Capability-neutral composition primitives supplied by xcron-kernel."""

from xcron.kernel.capability import (
    CAPABILITY_ENTRY_POINT_GROUP,
    KERNEL_API_VERSION,
    AssetDeclaration,
    Capability,
    CapabilityDescriptor,
    CapabilityHostProtocol,
    CapabilityProvides,
    CapabilityRegistration,
    CapabilityRequirement,
    CapabilitySelection,
)
from xcron.kernel.errors import (
    CapabilityAmbiguousError,
    CapabilityClosedError,
    CapabilityCollisionError,
    CapabilityCycleError,
    CapabilityError,
    CapabilityIncompatibleError,
    CapabilityMalformedError,
    CapabilityUnavailableError,
)
from xcron.kernel.host import CapabilityHost
from xcron.kernel.registry import CapabilityRegistry, CapabilitySnapshot
from xcron.kernel.resource_catalog import CapabilityResources

__all__ = [
    "CAPABILITY_ENTRY_POINT_GROUP",
    "KERNEL_API_VERSION",
    "AssetDeclaration",
    "Capability",
    "CapabilityAmbiguousError",
    "CapabilityClosedError",
    "CapabilityCollisionError",
    "CapabilityCycleError",
    "CapabilityDescriptor",
    "CapabilityError",
    "CapabilityHost",
    "CapabilityHostProtocol",
    "CapabilityIncompatibleError",
    "CapabilityMalformedError",
    "CapabilityProvides",
    "CapabilityRegistration",
    "CapabilityRegistry",
    "CapabilityRequirement",
    "CapabilityResources",
    "CapabilitySelection",
    "CapabilitySnapshot",
    "CapabilityUnavailableError",
]

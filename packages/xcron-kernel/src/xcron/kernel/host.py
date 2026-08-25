"""Lazy construction and lifecycle of a validated capability snapshot."""

from __future__ import annotations

from typing import TypeVar

from xcron.kernel.capability import Capability, CapabilityHostProtocol, CapabilityRegistration, CapabilitySelection
from xcron.kernel.errors import (
    CapabilityClosedError,
    CapabilityCycleError,
    CapabilityMalformedError,
    CapabilityUnavailableError,
)
from xcron.kernel.registry import CapabilityRegistry, CapabilitySnapshot


PortT = TypeVar("PortT")
_MISSING = object()


class CapabilityHost(CapabilityHostProtocol):
    """Build selected registrations once, only through declared kernel seams."""

    def __init__(self, registry: CapabilityRegistry, selection: CapabilitySelection | None = None) -> None:
        self._registry = registry
        self._snapshot = registry.snapshot(selection)
        self._selected = {
            capability.descriptor.capability: capability for capability in registry.selected(self._snapshot)
        }
        self._registrations: dict[str, CapabilityRegistration] = {}
        self._building: list[str] = []
        self._closed = False

    @property
    def registry(self) -> CapabilityRegistry:
        return self._registry

    @property
    def snapshot(self) -> CapabilitySnapshot:
        return self._snapshot

    def __enter__(self) -> CapabilityHost:
        self._guard()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        """Close constructed registrations in reverse dependency order once."""
        if self._closed:
            return
        for descriptor in reversed(self._snapshot.descriptors):
            registration = self._registrations.get(descriptor.capability)
            closer = getattr(registration, "close", None)
            if callable(closer):
                closer()
        self._closed = True

    def freeze(self) -> CapabilitySnapshot:
        """Construct every selected provider and validate its declared claims."""
        self._guard()
        for descriptor in self._snapshot.descriptors:
            self._registration(descriptor.capability)
        return self._snapshot

    def require(self, capability: str, port: type[PortT], *, port_id: str | None = None) -> PortT:
        """Return a runtime-checked port from the selected provider."""
        self._guard()
        registration = self._registration(capability)
        selected_port = self._select_port(capability, registration, port_id)
        try:
            satisfies = isinstance(selected_port, port)
        except TypeError as error:
            raise CapabilityMalformedError(
                f"Port token {port!r} for capability {capability!r} is not runtime-checkable.",
                "Pass a @runtime_checkable Protocol or a concrete type to CapabilityHost.require.",
            ) from error
        if not satisfies:
            raise CapabilityMalformedError(
                f"Capability {capability!r} port {port_id or '<only>'!r} does not satisfy {port.__name__}.",
                "Fix the provider registration to implement the declared port contract.",
            )
        return selected_port

    def _registration(self, capability: str) -> CapabilityRegistration:
        existing = self._registrations.get(capability, _MISSING)
        if existing is not _MISSING:
            return existing
        provider = self._selected.get(capability)
        if provider is None:
            self._registry.select(capability)
            raise CapabilityUnavailableError(  # pragma: no cover - select always raises above
                f"Capability {capability!r} is absent from this host snapshot.",
                "Construct a host with a snapshot that selects the requested capability.",
            )
        if capability in self._building:
            cycle = " -> ".join([*self._building, capability])
            raise CapabilityCycleError(
                f"Provider construction requested a runtime cycle: {cycle}.",
                "Build dependencies through an acyclic set of declared capability ports.",
            )
        self._building.append(capability)
        try:
            registration = provider.build(self)
            if not isinstance(registration, CapabilityRegistration):
                raise CapabilityMalformedError(
                    f"Capability {provider.id!r} did not return CapabilityRegistration.",
                    "Make the provider build function return its explicit registration.",
                )
            registered_claims = registration.claim_names()
            declared_claims = provider.descriptor.provides
            if any(
                set(registered) != set(declared)
                for (_category, registered), (_other_category, declared) in zip(
                    registered_claims.categories(),
                    declared_claims.categories(),
                    strict=True,
                )
            ):
                raise CapabilityMalformedError(
                    f"Capability {provider.id!r} registered claims that differ from its descriptor.",
                    "Make descriptor provides and registration claim names match exactly.",
                )
            self._registrations[capability] = registration
            return registration
        finally:
            self._building.pop()

    @staticmethod
    def _select_port(
        capability: str,
        registration: CapabilityRegistration,
        port_id: str | None,
    ) -> object:
        if port_id is None:
            if len(registration.ports) != 1:
                raise CapabilityMalformedError(
                    f"Capability {capability!r} exposes {len(registration.ports)} ports; no port_id was stated.",
                    "Pass the declared port_id explicitly when a capability exposes more than one port.",
                )
            return next(iter(registration.ports.values()))
        try:
            return registration.ports[port_id]
        except KeyError as error:
            raise CapabilityMalformedError(
                f"Capability {capability!r} did not register port {port_id!r}.",
                "Request a declared port id or fix the provider registration.",
            ) from error

    def _guard(self) -> None:
        if self._closed:
            raise CapabilityClosedError(
                "This capability host is closed.",
                "Open a new CapabilityHost before requesting a capability port.",
            )

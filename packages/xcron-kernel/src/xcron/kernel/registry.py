"""Discover and deterministically select installed capability providers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points

from xcron.kernel.capability import (
    CAPABILITY_ENTRY_POINT_GROUP,
    Capability,
    CapabilityDescriptor,
    CapabilitySelection,
)
from xcron.kernel.errors import (
    CapabilityAmbiguousError,
    CapabilityCollisionError,
    CapabilityCycleError,
    CapabilityMalformedError,
    CapabilityUnavailableError,
)


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    """The selected, dependency-ordered provider set for one host."""

    descriptors: tuple[CapabilityDescriptor, ...]

    def ids(self) -> tuple[str, ...]:
        return tuple(descriptor.id for descriptor in self.descriptors)

    def descriptor_for(self, capability: str) -> CapabilityDescriptor:
        for descriptor in self.descriptors:
            if descriptor.capability == capability:
                return descriptor
        raise CapabilityUnavailableError(
            f"No selected implementation provides capability {capability!r}.",
            "Install a provider or select an implementation that is installed.",
        )


class CapabilityRegistry:
    """Validated provider metadata indexed by replaceable capability name."""

    def __init__(self, capabilities: Iterable[Capability]) -> None:
        self._by_capability: dict[str, dict[str, Capability]] = {}
        for candidate in capabilities:
            if not isinstance(candidate, Capability):
                raise CapabilityMalformedError(
                    f"Discovered object {candidate!r} is not a Capability value.",
                    "Point the entry point at a xcron.kernel.Capability instance.",
                )
            candidate.descriptor.validate()
            claimed = self._by_capability.setdefault(candidate.descriptor.capability, {})
            implementation = candidate.descriptor.implementation
            if implementation in claimed:
                raise CapabilityCollisionError(
                    f"Two distributions claim capability implementation {candidate.id!r}.",
                    "Uninstall one conflicting provider or give it a distinct implementation identity.",
                )
            claimed[implementation] = candidate

    @classmethod
    def from_entry_points(
        cls,
        *,
        group: str = CAPABILITY_ENTRY_POINT_GROUP,
        discover: Callable[[str], Sequence[EntryPoint]] | None = None,
    ) -> CapabilityRegistry:
        """Load only installed provider entry points for the named group."""
        loader = _entry_points_for_group if discover is None else discover
        candidates: list[Capability] = []
        for point in sorted(loader(group), key=lambda item: (item.name, item.value)):
            try:
                candidate = point.load()
            except Exception as error:
                raise CapabilityMalformedError(
                    f"Capability entry point {point.name!r} could not be loaded: {error}.",
                    "Install a working provider wheel or remove its broken entry point.",
                ) from error
            if not isinstance(candidate, Capability):
                raise CapabilityMalformedError(
                    f"Capability entry point {point.name!r} did not return a Capability value.",
                    "Point it at a xcron.kernel.Capability value, not a provider implementation.",
                )
            candidates.append(candidate)
        return cls(candidates)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_capability))

    def implementations(self, capability: str) -> tuple[str, ...]:
        return tuple(sorted(self._by_capability.get(capability, {})))

    def select(self, capability: str, implementation: str | None = None) -> Capability:
        """Select one provider, refusing implicit resolution of ambiguity."""
        candidates = self._by_capability.get(capability)
        if not candidates:
            raise CapabilityUnavailableError(
                f"No installed implementation provides capability {capability!r}.",
                f"Install a wheel that advertises {capability!r} in {CAPABILITY_ENTRY_POINT_GROUP!r}.",
            )
        if implementation is not None:
            selected = candidates.get(implementation)
            if selected is None:
                available = ", ".join(sorted(candidates))
                raise CapabilityUnavailableError(
                    f"Implementation {implementation!r} of capability {capability!r} is not installed.",
                    f"Select one of the installed implementations: {available}.",
                )
            return selected
        if len(candidates) > 1:
            available = ", ".join(sorted(candidates))
            raise CapabilityAmbiguousError(
                f"Capability {capability!r} has multiple installed implementations: {available}.",
                f"Pass CapabilitySelection({capability}=...) to select one explicitly.",
            )
        return next(iter(candidates.values()))

    def snapshot(self, selection: CapabilitySelection | None = None) -> CapabilitySnapshot:
        """Validate selected providers and return deterministic dependency order."""
        chosen = selection or CapabilitySelection()
        selected: dict[str, Capability] = {}
        for capability in self.names():
            selected[capability] = self.select(capability, chosen.implementation_of(capability))
        for capability, implementation in chosen.items():
            if capability not in selected:
                self.select(capability, implementation)
        self._validate_requirements(selected)
        self._validate_claim_collisions(selected)
        return CapabilitySnapshot(
            tuple(candidate.descriptor for candidate in self._dependency_order(selected))
        )

    def selected(self, snapshot: CapabilitySnapshot) -> Iterator[Capability]:
        for descriptor in snapshot.descriptors:
            yield self.select(descriptor.capability, descriptor.implementation)

    def _validate_requirements(self, selected: dict[str, Capability]) -> None:
        for candidate in selected.values():
            for requirement in candidate.descriptor.requires:
                dependency = selected.get(requirement.capability)
                if dependency is None:
                    raise CapabilityUnavailableError(
                        f"Capability {candidate.id!r} requires absent capability {requirement.capability!r}.",
                        "Install the required provider before constructing this host.",
                    )
                if (
                    requirement.implementation is not None
                    and dependency.descriptor.implementation != requirement.implementation
                ):
                    raise CapabilityUnavailableError(
                        f"Capability {candidate.id!r} requires {requirement.capability}:{requirement.implementation}, "
                        f"but selected {dependency.id!r}.",
                        "Adjust CapabilitySelection or install the required implementation.",
                    )

    def _validate_claim_collisions(self, selected: dict[str, Capability]) -> None:
        claims: dict[tuple[str, str], str] = {}
        for candidate in selected.values():
            for category, names in candidate.descriptor.provides.categories():
                for name in names:
                    key = (category, name)
                    owner = claims.setdefault(key, candidate.id)
                    if owner != candidate.id:
                        raise CapabilityCollisionError(
                            f"Capability claim {category}:{name!r} is owned by both {owner!r} and {candidate.id!r}.",
                            "Select one provider or rename the overlapping public claim.",
                        )

    def _dependency_order(self, selected: dict[str, Capability]) -> tuple[Capability, ...]:
        ordered: list[Capability] = []
        active: list[str] = []
        visited: set[str] = set()

        def visit(capability: str) -> None:
            if capability in active:
                cycle = " -> ".join([*active, capability])
                raise CapabilityCycleError(
                    f"Selected capabilities have a dependency cycle: {cycle}.",
                    "Break the provider dependency cycle by depending on a narrower contract.",
                )
            if capability in visited:
                return
            active.append(capability)
            for requirement in sorted(selected[capability].descriptor.requires, key=lambda item: item.capability):
                visit(requirement.capability)
            active.pop()
            visited.add(capability)
            ordered.append(selected[capability])

        for capability in sorted(selected):
            visit(capability)
        return tuple(ordered)


def _entry_points_for_group(group: str) -> Sequence[EntryPoint]:
    """Use the modern metadata API while retaining older Python compatibility."""
    discovered = entry_points()
    if hasattr(discovered, "select"):
        return tuple(discovered.select(group=group))
    return tuple(discovered.get(group, ()))

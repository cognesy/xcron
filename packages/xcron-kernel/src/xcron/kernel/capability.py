"""Generic descriptor vocabulary for replaceable capability packages."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import re
from typing import Protocol, TypeVar

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from xcron.kernel.errors import CapabilityIncompatibleError, CapabilityMalformedError


CAPABILITY_ENTRY_POINT_GROUP = "xcron.capabilities"
KERNEL_API_VERSION = Version("1.0.0")

PortT = TypeVar("PortT")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    """One selected capability this provider needs before it can be built."""

    capability: str
    implementation: str | None = None


@dataclass(frozen=True, slots=True)
class CapabilityProvides:
    """Named claims a provider must register exactly once it is constructed."""

    ports: tuple[str, ...] = ()
    sdk_groups: tuple[str, ...] = ()
    cli_paths: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()

    def categories(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return (
            ("ports", self.ports),
            ("sdk_groups", self.sdk_groups),
            ("cli_paths", self.cli_paths),
            ("assets", self.assets),
        )


@dataclass(frozen=True, slots=True)
class AssetDeclaration:
    """A resource name and package-relative location promised by a provider."""

    name: str
    relative_path: str


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    """Static identity and claims for one provider implementation."""

    capability: str
    implementation: str
    version: str
    kernel_api: str
    requires: tuple[CapabilityRequirement, ...] = ()
    provides: CapabilityProvides = field(default_factory=CapabilityProvides)
    assets: tuple[AssetDeclaration, ...] = ()

    @property
    def id(self) -> str:
        return f"{self.capability}:{self.implementation}"

    def validate(self) -> None:
        for field_name, value in (
            ("capability", self.capability),
            ("implementation", self.implementation),
        ):
            if not _IDENTIFIER.fullmatch(value):
                raise CapabilityMalformedError(
                    f"{field_name} {value!r} in descriptor {self.id!r} is invalid.",
                    "Use lower-case letters, digits, and hyphens, starting with a letter.",
                )
        try:
            Version(self.version)
        except InvalidVersion as error:
            raise CapabilityMalformedError(
                f"Capability {self.id!r} has invalid version {self.version!r}.",
                "Publish a PEP 440 package version in the descriptor.",
            ) from error
        try:
            supported_kernel = SpecifierSet(self.kernel_api)
        except InvalidSpecifier as error:
            raise CapabilityMalformedError(
                f"Capability {self.id!r} has invalid kernel API range {self.kernel_api!r}.",
                "Declare a valid PEP 440 specifier range for the kernel API.",
            ) from error
        if KERNEL_API_VERSION not in supported_kernel:
            raise CapabilityIncompatibleError(
                f"Capability {self.id!r} supports kernel API {self.kernel_api!r}, not {KERNEL_API_VERSION}.",
                "Install a compatible provider version or select a compatible implementation.",
            )
        self._validate_unique("requires", tuple(item.capability for item in self.requires))
        for category, values in self.provides.categories():
            self._validate_unique(category, values)
        self._validate_unique("asset names", tuple(asset.name for asset in self.assets))
        for asset in self.assets:
            if not asset.relative_path or asset.relative_path.startswith("/") or ".." in asset.relative_path.split("/"):
                raise CapabilityMalformedError(
                    f"Capability {self.id!r} declares unsafe asset path {asset.relative_path!r}.",
                    "Declare a non-empty package-relative path that does not leave the package.",
                )
        if set(self.provides.assets) != {asset.name for asset in self.assets}:
            raise CapabilityMalformedError(
                f"Capability {self.id!r} asset claims do not match asset declarations.",
                "List every declared asset name once in provides.assets.",
            )

    def _validate_unique(self, category: str, values: tuple[str, ...]) -> None:
        if len(values) != len(set(values)) or any(not value for value in values):
            raise CapabilityMalformedError(
                f"Capability {self.id!r} has duplicate or blank {category} claims.",
                "Declare each non-empty claim exactly once.",
            )


class CapabilityHostProtocol(Protocol):
    """The only composition API visible while one provider is built."""

    def require(self, capability: str, port: type[PortT], *, port_id: str | None = None) -> PortT:
        """Return one selected capability port, constructing it at most once."""
        ...


@dataclass(frozen=True, slots=True)
class CapabilityRegistration:
    """The exact public claims registered by one constructed provider."""

    ports: Mapping[str, object] = field(default_factory=dict)
    sdk_groups: Mapping[str, object] = field(default_factory=dict)
    cli_paths: Mapping[str, object] = field(default_factory=dict)
    assets: Mapping[str, object] = field(default_factory=dict)

    def claim_names(self) -> CapabilityProvides:
        return CapabilityProvides(
            ports=tuple(sorted(self.ports)),
            sdk_groups=tuple(sorted(self.sdk_groups)),
            cli_paths=tuple(sorted(self.cli_paths)),
            assets=tuple(sorted(self.assets)),
        )


@dataclass(frozen=True, slots=True)
class Capability:
    """One installed but not-yet-constructed provider implementation."""

    descriptor: CapabilityDescriptor
    build: Callable[[CapabilityHostProtocol], CapabilityRegistration]

    @property
    def id(self) -> str:
        return self.descriptor.id


class CapabilitySelection:
    """Explicit choices for contested capability implementations."""

    def __init__(self, **implementations: str) -> None:
        self._implementations = dict(implementations)

    def implementation_of(self, capability: str) -> str | None:
        return self._implementations.get(capability)

    def items(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._implementations.items()))

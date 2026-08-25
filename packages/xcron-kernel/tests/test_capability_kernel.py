"""Kernel-only tests for capability discovery, selection, and composition."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest

from xcron.kernel import (
    CAPABILITY_ENTRY_POINT_GROUP,
    AssetDeclaration,
    Capability,
    CapabilityAmbiguousError,
    CapabilityClosedError,
    CapabilityCollisionError,
    CapabilityCycleError,
    CapabilityDescriptor,
    CapabilityHost,
    CapabilityIncompatibleError,
    CapabilityMalformedError,
    CapabilityProvides,
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityRequirement,
    CapabilityResources,
    CapabilitySelection,
    CapabilityUnavailableError,
)


@runtime_checkable
class GreetingPort(Protocol):
    def greet(self) -> str: ...


class Greeter:
    def __init__(self, greeting: str) -> None:
        self._greeting = greeting

    def greet(self) -> str:
        return self._greeting


@dataclass(frozen=True)
class FakeEntryPoint:
    name: str
    loaded: object
    value: str = "test:capability"

    def load(self) -> object:
        return self.loaded


def capability(
    name: str,
    implementation: str,
    greeting: str,
    *,
    requires: tuple[CapabilityRequirement, ...] = (),
    kernel_api: str = ">=1,<2",
    port_name: str | None = None,
) -> Capability:
    claimed_port = port_name or name
    descriptor = CapabilityDescriptor(
        capability=name,
        implementation=implementation,
        version="1.0.0",
        kernel_api=kernel_api,
        requires=requires,
        provides=CapabilityProvides(ports=(claimed_port,)),
    )
    return Capability(
        descriptor,
        build=lambda _host: CapabilityRegistration(ports={claimed_port: Greeter(greeting)}),
    )


def host(*providers: Capability, selection: CapabilitySelection | None = None) -> CapabilityHost:
    return CapabilityHost(CapabilityRegistry(providers), selection)


def test_lone_implementation_is_selected_and_built_once() -> None:
    builds: list[str] = []
    provider = capability("greeting", "english", "hello")
    provider = Capability(
        provider.descriptor,
        build=lambda _host: (
            builds.append("built")
            or CapabilityRegistration(ports={"greeting": Greeter("hello")})
        ),
    )
    composed = host(provider)

    assert composed.snapshot.ids() == ("greeting:english",)
    assert composed.require("greeting", GreetingPort).greet() == "hello"
    assert composed.require("greeting", GreetingPort).greet() == "hello"
    assert builds == ["built"]


def test_multiple_implementations_require_explicit_selection() -> None:
    with pytest.raises(CapabilityAmbiguousError) as failure:
        host(capability("greeting", "english", "hello"), capability("greeting", "polish", "czesc"))

    assert failure.value.code == "capability_ambiguous"
    assert "english, polish" in failure.value.message

    composed = host(
        capability("greeting", "english", "hello"),
        capability("greeting", "polish", "czesc"),
        selection=CapabilitySelection(greeting="polish"),
    )
    assert composed.require("greeting", GreetingPort).greet() == "czesc"


def test_missing_provider_and_unknown_selection_are_structured() -> None:
    with pytest.raises(CapabilityUnavailableError) as absent:
        host().require("greeting", GreetingPort)
    assert absent.value.code == "capability_unavailable"
    assert CAPABILITY_ENTRY_POINT_GROUP in absent.value.remedy

    with pytest.raises(CapabilityUnavailableError) as selection:
        host(
            capability("greeting", "english", "hello"),
            selection=CapabilitySelection(greeting="missing"),
        )
    assert "english" in selection.value.remedy


def test_duplicate_identity_and_public_claims_are_rejected() -> None:
    with pytest.raises(CapabilityCollisionError):
        CapabilityRegistry((capability("greeting", "english", "one"), capability("greeting", "english", "two")))

    with pytest.raises(CapabilityCollisionError) as collision:
        host(
            capability("first", "local", "one", port_name="shared"),
            capability("second", "local", "two", port_name="shared"),
        )
    assert "ports:'shared'" in collision.value.message


def test_declared_dependencies_are_ordered_and_runtime_dependencies_use_the_host() -> None:
    greeting = capability("greeting", "english", "hello")
    descriptor = CapabilityDescriptor(
        capability="shouting",
        implementation="upper",
        version="1.0.0",
        kernel_api=">=1,<2",
        requires=(CapabilityRequirement("greeting"),),
        provides=CapabilityProvides(ports=("shouting",)),
    )
    shouting = Capability(
        descriptor,
        build=lambda composed: CapabilityRegistration(
            ports={"shouting": Greeter(composed.require("greeting", GreetingPort).greet().upper())}
        ),
    )

    composed = host(shouting, greeting)
    assert composed.snapshot.ids() == ("greeting:english", "shouting:upper")
    assert composed.require("shouting", GreetingPort).greet() == "HELLO"


def test_missing_and_cyclic_declared_dependencies_fail_before_building() -> None:
    with pytest.raises(CapabilityUnavailableError) as missing:
        host(
            capability(
                "shouting",
                "upper",
                "hello",
                requires=(CapabilityRequirement("greeting"),),
            )
        )
    assert "requires absent capability" in missing.value.message

    with pytest.raises(CapabilityCycleError) as cycle:
        host(
            capability("left", "one", "one", requires=(CapabilityRequirement("right"),)),
            capability("right", "two", "two", requires=(CapabilityRequirement("left"),)),
        )
    assert "left -> right -> left" in cycle.value.message


def test_incompatible_malformed_and_unmatched_provider_registration_fail() -> None:
    with pytest.raises(CapabilityIncompatibleError):
        CapabilityRegistry((capability("greeting", "future", "hello", kernel_api=">=2"),))

    malformed = CapabilityDescriptor(
        capability="Greeting",
        implementation="english",
        version="1.0.0",
        kernel_api=">=1,<2",
    )
    with pytest.raises(CapabilityMalformedError):
        CapabilityRegistry((Capability(malformed, lambda _host: CapabilityRegistration()),))

    provider = capability("greeting", "broken", "hello")
    broken = Capability(provider.descriptor, lambda _host: CapabilityRegistration(ports={"other": Greeter("hello")}))
    with pytest.raises(CapabilityMalformedError) as registration:
        host(broken).freeze()
    assert "registered claims" in registration.value.message


def test_registration_claim_order_does_not_change_its_declared_ownership() -> None:
    descriptor = CapabilityDescriptor(
        capability="commands",
        implementation="local",
        version="1.0.0",
        kernel_api=">=1,<2",
        provides=CapabilityProvides(cli_paths=("validate", "plan")),
    )
    provider = Capability(
        descriptor,
        lambda _host: CapabilityRegistration(cli_paths={"validate": None, "plan": None}),
    )

    assert host(provider).freeze().ids() == ("commands:local",)


def test_discovery_loads_only_capability_values_and_reports_bad_metadata() -> None:
    provider = capability("greeting", "english", "hello")
    registry = CapabilityRegistry.from_entry_points(
        discover=lambda group: (FakeEntryPoint("english", provider),) if group == CAPABILITY_ENTRY_POINT_GROUP else ()
    )
    assert registry.implementations("greeting") == ("english",)

    with pytest.raises(CapabilityMalformedError) as failure:
        CapabilityRegistry.from_entry_points(discover=lambda _group: (FakeEntryPoint("bad", object()),))
    assert "did not return a Capability" in failure.value.message


def test_runtime_cycles_port_shape_and_closed_hosts_are_rejected() -> None:
    left_descriptor = CapabilityDescriptor(
        capability="left",
        implementation="one",
        version="1.0.0",
        kernel_api=">=1,<2",
        provides=CapabilityProvides(ports=("left",)),
    )
    right_descriptor = CapabilityDescriptor(
        capability="right",
        implementation="two",
        version="1.0.0",
        kernel_api=">=1,<2",
        provides=CapabilityProvides(ports=("right",)),
    )
    left = Capability(
        left_descriptor,
        lambda composed: CapabilityRegistration(ports={"left": composed.require("right", GreetingPort)}),
    )
    right = Capability(
        right_descriptor,
        lambda composed: CapabilityRegistration(ports={"right": composed.require("left", GreetingPort)}),
    )
    with pytest.raises(CapabilityCycleError):
        host(left, right).require("left", GreetingPort)

    composed = host(capability("greeting", "english", "hello"))
    composed.close()
    with pytest.raises(CapabilityClosedError):
        composed.require("greeting", GreetingPort)


def test_resources_stay_inside_their_own_distribution() -> None:
    resources = CapabilityResources("xcron.kernel")
    assert resources.read_text("resources/kernel-api.txt") == "1.0.0\n"
    with pytest.raises(CapabilityMalformedError):
        resources.read_text("../pyproject.toml")


def test_kernel_source_has_no_product_or_terminal_dependency() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "xcron" / "kernel"
    forbidden = {"pydantic", "yaml", "xcfg", "structlog", "typer", "rich", "toon", "subprocess"}
    for source in source_root.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module)
        assert not any(name == "xcron.capabilities" or name.startswith("xcron.capabilities.") for name in imports)
        assert not any(name == item or name.startswith(f"{item}.") for name in imports for item in forbidden)

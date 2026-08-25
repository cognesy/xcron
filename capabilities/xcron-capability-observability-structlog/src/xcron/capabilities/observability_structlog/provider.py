"""Installed entry point and outcome-sink adapter for structured observability."""

from __future__ import annotations

from xcron.capabilities.observability_structlog.observability import get_logger
from xcron.contracts import InvocationContext, ObservabilityPort, OutcomeSink
from xcron.kernel import (
    AssetDeclaration,
    Capability,
    CapabilityDescriptor,
    CapabilityProvides,
    CapabilityRegistration,
)


class StructlogOutcomeSink:
    """Best-effort log projection that can never interrupt a product action."""

    def record(self, counter: str, amount: int = 1) -> None:
        try:
            event, separator, action = counter.partition(":")
            if separator and event in {"action_started", "action_finished", "action_failed"}:
                get_logger("xcron.action").info(event, action=action, amount=amount)
            else:
                get_logger("xcron.outcome").info("outcome_recorded", counter=counter, amount=amount)
        except Exception:
            return None


class StructlogObservabilityProvider:
    """Provide the public outcome sink without owning product persistence."""

    def outcome_sink(self, context: InvocationContext) -> OutcomeSink:
        del context
        # Configure for the current process stream before another provider can
        # issue a standard-library warning during workspace resolution.
        get_logger("xcron.outcome")
        return StructlogOutcomeSink()


DESCRIPTOR = CapabilityDescriptor(
    capability="observability",
    implementation="structlog",
    version="0.1.1",
    kernel_api=">=1,<2",
    provides=CapabilityProvides(ports=("observability",), assets=("logging-default",)),
    assets=(AssetDeclaration("logging-default", "resources/logging/default.yaml"),),
)


def _build(_: object) -> CapabilityRegistration:
    return CapabilityRegistration(
        ports={"observability": StructlogObservabilityProvider()},
        assets={"logging-default": "resources/logging/default.yaml"},
    )


CAPABILITY = Capability(DESCRIPTOR, _build)

assert isinstance(StructlogObservabilityProvider(), ObservabilityPort)

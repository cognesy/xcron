"""A no-IO alternate metrics provider for package replacement proofs."""

from __future__ import annotations

from xcron.contracts import (
    InvocationContext,
    MetricsPort,
    MetricsResetResult,
    MetricsResult,
    NullOutcomeSink,
    OutcomeSink,
)
from xcron.kernel import Capability, CapabilityDescriptor, CapabilityProvides, CapabilityRegistration


class TestMetricsProvider:
    """A deterministic provider which keeps replacement tests machine-independent."""

    def show(self, context: InvocationContext) -> MetricsResult:
        del context
        return MetricsResult(
            path="test://xcron/metrics",
            version=1,
            created_at="2000-01-01T00:00:00+00:00",
            updated_at="2000-01-01T00:00:00+00:00",
            counters={"alternate_provider": 1},
        )

    def reset(self, context: InvocationContext) -> MetricsResetResult:
        shown = self.show(context)
        return MetricsResetResult(
            path=shown.path,
            version=shown.version,
            created_at=shown.created_at,
            updated_at=shown.updated_at,
            counters={},
            previous_counters=shown.counters,
        )

    def outcome_sink(self, context: InvocationContext) -> OutcomeSink:
        del context
        return NullOutcomeSink()


DESCRIPTOR = CapabilityDescriptor(
    capability="metrics",
    implementation="test",
    version="0.1.1",
    kernel_api=">=1,<2",
    provides=CapabilityProvides(ports=("metrics",)),
)


def _build(host: object) -> CapabilityRegistration:
    del host
    return CapabilityRegistration(ports={"metrics": TestMetricsProvider()})


CAPABILITY = Capability(DESCRIPTOR, _build)

assert isinstance(TestMetricsProvider(), MetricsPort)

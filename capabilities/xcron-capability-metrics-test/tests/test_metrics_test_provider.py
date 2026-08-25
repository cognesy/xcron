"""The alternate provider is portable and does not require a workspace."""

from xcron.capabilities.metrics_test.provider import CAPABILITY
from xcron.contracts import InvocationContext, MetricsPort, Settings, XcronOptions


def test_test_metrics_provider_is_a_port_and_is_deterministic(tmp_path) -> None:
    provider = CAPABILITY.build(object()).ports["metrics"]
    assert isinstance(provider, MetricsPort)

    context = InvocationContext(XcronOptions.create(tmp_path), None, Settings())
    assert provider.show(context).counters == {"alternate_provider": 1}
    assert provider.reset(context).previous_counters == {"alternate_provider": 1}

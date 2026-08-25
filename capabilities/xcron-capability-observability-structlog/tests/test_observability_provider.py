"""Contract and configuration checks for the structlog provider wheel."""

from __future__ import annotations

from xcron.capabilities.observability_structlog.api import load_logging_config
from xcron.capabilities.observability_structlog.provider import CAPABILITY
from xcron.contracts import InvocationContext, ObservabilityPort, Settings, XcronOptions
from xcron.kernel import CapabilityHost, CapabilityRegistry


def test_provider_loads_its_own_resource_with_explicit_overrides() -> None:
    """No process environment is needed to choose logging behaviour."""
    config = load_logging_config(
        environ={"XCRON_LOG_LEVEL": "debug", "XCRON_LOG_FORMAT": "json"}
    )

    assert config.level == "DEBUG"
    assert config.format == "json"


def test_provider_returns_a_best_effort_contract_sink() -> None:
    """The kernel reaches observability only through its declared port."""
    host = CapabilityHost(CapabilityRegistry((CAPABILITY,)))
    provider = host.require("observability", ObservabilityPort)

    sink = provider.outcome_sink(
        InvocationContext(options=XcronOptions.create(), workspace=None, settings=Settings())
    )
    sink.record("provider_test")

    assert host.freeze().ids() == ("observability:structlog",)

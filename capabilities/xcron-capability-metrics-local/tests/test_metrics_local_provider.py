"""Resilience tests for the isolated local metrics provider."""

from __future__ import annotations

from pathlib import Path

from xcron.capabilities.metrics_local.provider import CAPABILITY as METRICS
from xcron.capabilities.workspace_local.provider import CAPABILITY as WORKSPACE
from xcron.contracts import InvocationContext, MetricsPort, Settings, XcronHome, XcronOptions
from xcron.kernel import CapabilityHost, CapabilityRegistry


class HomeWorkspace:
    def __init__(self, home: Path) -> None:
        self._home = home

    def home(self, root=None) -> XcronHome:
        return XcronHome(self._home, self._home / "schedules", self._home / "schedules/default.yaml", self._home / "metrics/metrics.json", self._home / "marker.toml")


def _context(tmp_path: Path) -> InvocationContext:
    return InvocationContext(XcronOptions.create(tmp_path), None, Settings())


def test_metrics_show_reset_and_context_outcome_sink_are_best_effort(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XCRON_HOME", str(tmp_path))
    host = CapabilityHost(CapabilityRegistry((WORKSPACE, METRICS)))
    provider = host.require("metrics", MetricsPort)
    assert isinstance(provider, MetricsPort)
    context = _context(tmp_path)

    sink = provider.outcome_sink(context)
    sink.record("scheduler.apply")
    shown = provider.show(context)
    reset = provider.reset(context)

    assert shown.counters == {"scheduler.apply": 1}
    assert reset.previous_counters == {"scheduler.apply": 1}
    assert provider.show(context).counters == {}
    assert host.freeze().ids() == ("workspace:local", "metrics:local")


def test_store_read_and_write_failures_do_not_escape(tmp_path: Path) -> None:
    home = tmp_path / "home"
    broken_path = home / "metrics"
    broken_path.mkdir(parents=True)
    (broken_path / "metrics.json").mkdir()
    provider = METRICS.build(type("Host", (), {"require": lambda _, *args, **kwargs: HomeWorkspace(home)})()).ports["metrics"]
    context = _context(tmp_path)

    provider.outcome_sink(context).record("must-not-raise")
    shown = provider.show(context)
    reset = provider.reset(context)

    assert shown.counters == {}
    assert reset.previous_counters == {}

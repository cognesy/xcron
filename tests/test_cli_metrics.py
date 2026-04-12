from __future__ import annotations

import json

from apps.cli.main import main
from libs.services.metrics import MetricsService


def test_metrics_show_and_reset_use_xcron_home(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XCRON_HOME", str(tmp_path))
    MetricsService().increment("ticks.started")

    path = tmp_path / "metrics" / "metrics.json"
    assert path.exists()

    assert main(["metrics", "show", "--output", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counters"]["ticks.started"] == 1

    assert main(["metrics", "reset", "--output", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counters"] == {}
    assert payload["previous_counters"]["ticks.started"] == 1

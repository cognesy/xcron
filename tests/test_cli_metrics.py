from __future__ import annotations

import json

from xcron_cli.main import main


def test_metrics_show_and_reset_use_xcron_home(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XCRON_HOME", str(tmp_path))

    path = tmp_path / "metrics" / "metrics.json"
    assert main(["metrics", "reset", "--output", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counters"] == {}
    assert payload["path"] == str(path)
    assert path.exists()

    assert main(["metrics", "show", "--output", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == str(path)

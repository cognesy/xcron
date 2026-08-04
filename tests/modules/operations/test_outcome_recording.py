"""Operations as the single writer of the metrics state family.

`record_outcome` is the only public write. These tests pin its behaviour from
the module surface, including the property reconciliation depends on: recording
never raises, so a failing evidence sink cannot fail a convergence run.
"""

from __future__ import annotations

from pathlib import Path

from xcron.capabilities.operations.api import record_outcome, reset_metrics, show_metrics


def test_recording_an_outcome_creates_and_accumulates_the_store(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("XCRON_HOME", str(tmp_path))

    record_outcome("apply.calls")
    record_outcome("apply.calls")
    record_outcome("jobs.applied", 3)

    result = show_metrics()

    assert result.path == str((tmp_path / "metrics" / "metrics.json").resolve())
    assert result.counters == {"apply.calls": 2, "jobs.applied": 3}
    assert result.version == 1


def test_reset_clears_the_counters_and_reports_what_was_there(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XCRON_HOME", str(tmp_path))
    record_outcome("status.calls")

    result = reset_metrics()

    assert result.counters == {}
    assert result.previous_counters == {"status.calls": 1}
    assert show_metrics().counters == {}


def test_recording_never_raises_when_the_store_cannot_be_written(
    tmp_path: Path, monkeypatch
) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("XCRON_HOME", str(blocked))

    record_outcome("apply.calls")


def test_a_corrupt_store_reads_back_as_empty_rather_than_failing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("XCRON_HOME", str(tmp_path))
    metrics_path = tmp_path / "metrics" / "metrics.json"
    metrics_path.parent.mkdir(parents=True)
    metrics_path.write_text("{ not json", encoding="utf-8")

    assert show_metrics().counters == {}

    record_outcome("apply.calls")

    assert show_metrics().counters == {"apply.calls": 1}

"""`project-state.json` as a promise, not as an implementation detail.

This file is left on other people's disks, so a later xcron has to be able to
read what this one wrote. That makes its shape a contract even though nothing
outside this module ever opens it.

The tests pin the literal key set rather than round-tripping through the writer
— a round trip agrees with itself no matter what changed. A failure here is not
a test to update: it means the durable format moved, and moving it needs a
migration path, not an edit.

The test lives in reconciliation's own lane because reconciliation owns the
file. Reaching its state writer from a shared directory would mean widening the
module's public surface for the benefit of a test, which is the opposite of
what that surface is for.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xcron_libs.capabilities.reconciliation.contracts import DeployedJobState, ProjectState
from xcron_libs.capabilities.reconciliation.state_store import (
    STATE_FILENAME,
    load_project_state,
    resolve_project_state_path,
    save_project_state,
)

TOP_LEVEL_KEYS = {"project_id", "backend", "manifest_hash", "updated_at", "jobs"}

DEPLOYED_JOB_KEYS = {
    "qualified_id",
    "job_id",
    "artifact_id",
    "backend",
    "enabled",
    "desired_hash",
    "definition_hash",
    "observed_hash",
    "label",
    "artifact_path",
    "wrapper_path",
    "stdout_log_path",
    "stderr_log_path",
    "event_log_path",
    "last_applied_at",
}

#: The keys a document has always had to carry. Everything else is optional and
#: must stay optional, or an older file stops loading.
REQUIRED_JOB_KEYS = {
    "qualified_id",
    "job_id",
    "artifact_id",
    "backend",
    "enabled",
    "desired_hash",
}


@pytest.fixture()
def written_state(tmp_path: Path) -> Path:
    state = ProjectState(
        project_id="demo",
        backend="launchd",
        manifest_hash="sha256:manifest",
        jobs=(
            DeployedJobState(
                qualified_id="demo.alpha",
                job_id="alpha",
                artifact_id="demo.alpha",
                backend="launchd",
                enabled=True,
                desired_hash="sha256:desired",
            ),
        ),
        updated_at="2026-08-04T00:00:00+00:00",
    )
    return save_project_state(state, state_root=tmp_path)


def test_the_state_file_lands_where_the_workspace_layout_says(tmp_path: Path) -> None:
    path = resolve_project_state_path("demo", state_root=tmp_path)

    assert path == tmp_path / "projects" / "demo" / STATE_FILENAME
    assert STATE_FILENAME == "project-state.json"


def test_the_document_carries_exactly_these_top_level_keys(written_state: Path) -> None:
    payload = json.loads(written_state.read_text(encoding="utf-8"))

    assert set(payload) == TOP_LEVEL_KEYS


def test_each_deployed_job_carries_exactly_these_keys(written_state: Path) -> None:
    payload = json.loads(written_state.read_text(encoding="utf-8"))

    assert [set(job) for job in payload["jobs"]] == [DEPLOYED_JOB_KEYS]


def test_the_document_is_written_deterministically(written_state: Path) -> None:
    """Sorted keys and stable indentation, so two equal states diff as equal."""
    text = written_state.read_text(encoding="utf-8")

    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True)


def test_a_document_holding_only_the_required_keys_still_loads(tmp_path: Path) -> None:
    path = resolve_project_state_path("legacy", state_root=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "project_id": "legacy",
                "backend": "cron",
                "manifest_hash": None,
                "jobs": [dict.fromkeys(REQUIRED_JOB_KEYS, "x") | {"enabled": True}],
            }
        ),
        encoding="utf-8",
    )

    state = load_project_state("legacy", "cron", state_root=tmp_path)

    assert state.jobs[0].wrapper_path is None
    assert state.updated_at is None


def test_a_missing_state_file_reads_as_an_empty_baseline(tmp_path: Path) -> None:
    state = load_project_state("absent", "cron", state_root=tmp_path)

    assert state == ProjectState(
        project_id="absent", backend="cron", manifest_hash=None, jobs=()
    )


def test_jobs_are_stored_in_a_stable_order(tmp_path: Path) -> None:
    """Ordering is part of the format: an unordered list diffs against itself."""
    jobs = tuple(
        DeployedJobState(
            qualified_id=f"demo.{name}",
            job_id=name,
            artifact_id=f"demo.{name}",
            backend="cron",
            enabled=True,
            desired_hash="sha256:desired",
        )
        for name in ("zulu", "alpha", "mike")
    )
    save_project_state(
        ProjectState(project_id="demo", backend="cron", manifest_hash=None, jobs=jobs),
        state_root=tmp_path,
    )

    reloaded = load_project_state("demo", "cron", state_root=tmp_path)

    assert [job.job_id for job in reloaded.jobs] == ["alpha", "mike", "zulu"]

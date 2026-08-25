"""Black-box compatibility promises for the capability-package migration.

These tests name only the public ``xcron`` SDK or invoke the console command.
They deliberately do not reach an action, adapter, renderer, or state-store
module: the package split may replace each of those without changing this
corpus.  The concrete literals below are a migration baseline, not snapshots
that should be casually updated when an implementation moves.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import plistlib
import subprocess
import textwrap

import pytest

from xcron.sdk import JobCreateRequest, JobUpdateRequest, ScheduleRequest, Xcron


ROOT = Path(__file__).resolve().parents[2]

MANIFEST = textwrap.dedent(
    """\
    version: 1
    project:
      id: compatibility-demo
    defaults:
      working_dir: .
      shell: /bin/sh
    jobs:
      - id: ping_job
        schedule:
          cron: "*/5 * * * *"
        command: echo ping
    """
)

STATE_KEYS = {"project_id", "backend", "manifest_hash", "updated_at", "jobs"}
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


@pytest.fixture()
def compatible_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make one project whose native writes are safely redirected to files."""
    project = tmp_path / "project"
    manifest_path = project / "resources" / "schedules" / "default.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(MANIFEST, encoding="utf-8")

    state_root = tmp_path / "state"
    crontab_path = tmp_path / "crontab"
    crontab_path.write_text("# externally owned entry\n", encoding="utf-8")
    monkeypatch.setenv("XCRON_HOME", str(tmp_path / "xcron-home"))
    monkeypatch.setenv("XCRON_STATE_ROOT", str(state_root))
    monkeypatch.setenv("XCRON_CRONTAB_PATH", str(crontab_path))
    monkeypatch.setenv("XCRON_MANAGE_CRONTAB", "0")
    monkeypatch.setenv("XCRON_MANAGE_LAUNCHCTL", "0")
    return project


def _cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the public development console script as a separate process."""
    return subprocess.run(
        ["uv", "run", "--project", str(ROOT), "xcron", *arguments],
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_output_formats_and_usage_errors_are_publicly_stable(
    compatible_project: Path,
) -> None:
    validation = _cli(
        "validate",
        "--project",
        str(compatible_project),
        "--output",
        "json",
    )

    assert validation.returncode == 0, validation.stderr
    validation_payload = json.loads(validation.stdout)
    assert set(validation_payload) == {
        "errors",
        "jobs",
        "manifest",
        "manifest_hash",
        "project",
        "valid",
        "warnings",
    }
    assert {key: value for key, value in validation_payload.items() if key != "manifest_hash"} == {
        "errors": 0,
        "jobs": 1,
        "manifest": str(compatible_project / "resources" / "schedules" / "default.yaml"),
        "project": str(compatible_project),
        "valid": True,
        "warnings": 0,
    }
    assert len(validation_payload["manifest_hash"]) == 64

    plan = _cli("plan", "--project", str(compatible_project), "--backend", "cron")
    assert plan.returncode == 0, plan.stderr
    assert "backend: cron" in plan.stdout
    assert "changes[1,]{kind,id,reason}:" in plan.stdout

    unknown_backend = _cli(
        "plan",
        "--project",
        str(compatible_project),
        "--backend",
        "not-a-provider",
        "--output",
        "json",
    )
    assert unknown_backend.returncode == 2
    assert json.loads(unknown_backend.stdout) == {
        "code": "usage_error",
        "details": [],
        "help": [],
        "kind": "error",
        "message": "unsupported scheduler backend: not-a-provider (available: cron, launchd)",
    }


def test_typed_sdk_mutation_and_cron_artifacts_are_stable(
    compatible_project: Path,
) -> None:
    state_root = Path(os.environ["XCRON_STATE_ROOT"])
    crontab_path = Path(os.environ["XCRON_CRONTAB_PATH"])

    with Xcron.open(
        compatible_project,
        backend="cron",
        platform="linux",
        state_root=state_root,
        crontab_path=crontab_path,
        manage_crontab=False,
    ) as client:
        added = client.jobs.add(
            JobCreateRequest(
                job_id="cleanup_job",
                command="echo cleanup",
                schedule=ScheduleRequest.every("1h"),
                env={"MODE": "safe"},
            )
        )
        updated = client.jobs.update(
            "ping_job",
            JobUpdateRequest(command="echo refreshed", schedule=ScheduleRequest.cron("0 * * * *")),
        )
        applied = client.schedules.apply()

    assert added.valid is True
    assert updated.valid is True
    assert applied.valid is True

    manifest_text = (compatible_project / "resources" / "schedules" / "default.yaml").read_text(
        encoding="utf-8"
    )
    assert "id: cleanup_job" in manifest_text
    assert "every: 1h" in manifest_text
    assert "MODE: safe" in manifest_text
    assert "command: echo refreshed" in manifest_text
    assert "cron: 0 * * * *" in manifest_text

    assert crontab_path.read_text(encoding="utf-8") == "# externally owned entry\n"
    state_path = state_root / "projects" / "compatibility-demo" / "project-state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(payload) == STATE_KEYS
    assert [job["job_id"] for job in payload["jobs"]] == ["cleanup_job", "ping_job"]
    assert all(set(job) == DEPLOYED_JOB_KEYS for job in payload["jobs"])
    assert all(len(job["desired_hash"]) == 64 for job in payload["jobs"])
    assert all(
        not any(
            line.startswith("xcron ")
            for line in Path(job["wrapper_path"]).read_text(encoding="utf-8").splitlines()
        )
        for job in payload["jobs"]
    )


def test_launchd_artifact_identity_is_stable(compatible_project: Path) -> None:
    state_root = Path(os.environ["XCRON_STATE_ROOT"])
    launch_agents_dir = compatible_project.parent / "LaunchAgents"

    with Xcron.open(
        compatible_project,
        backend="launchd",
        platform="darwin",
        state_root=state_root,
        launch_agents_dir=launch_agents_dir,
        manage_launchctl=False,
    ) as client:
        result = client.schedules.apply()

    assert result.valid is True
    plist_path = launch_agents_dir / "com.xcron.compatibility-demo.ping_job.plist"
    plist = plistlib.loads(plist_path.read_bytes())
    assert plist["Label"] == "com.xcron.compatibility-demo.ping_job"
    assert plist["EnvironmentVariables"]["XCRON_QUALIFIED_ID"] == "compatibility-demo.ping_job"
    assert plist["ProgramArguments"] == [
        str(state_root / "projects" / "compatibility-demo" / "wrappers" / "compatibility-demo.ping_job.sh")
    ]

"""Contract tests for the isolated YAML-only jobs provider."""

from __future__ import annotations

from pathlib import Path

from xcron.capabilities.jobs_manifest.provider import CAPABILITY as JOBS
from xcron.capabilities.manifest_yaml.provider import CAPABILITY as MANIFEST
from xcron.capabilities.scheduler_native.provider import CAPABILITY as SCHEDULER
from xcron.capabilities.workspace_local.provider import CAPABILITY as WORKSPACE
from xcron.contracts import (
    InvocationContext,
    JobCreateRequest,
    JobLookupRequest,
    JobManagementPort,
    JobUpdateRequest,
    ProjectRequest,
    ProjectWorkspace,
    ScheduleRequest,
    Settings,
    XcronOptions,
)
from xcron.kernel import CapabilityHost, CapabilityRegistry


MANIFEST_TEXT = """\
version: 1
project:
  id: jobs-provider
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: archive
    command: echo archive
    schedule:
      cron: "0 * * * *"
"""


def _context(tmp_path: Path) -> InvocationContext:
    schedules = tmp_path / "resources" / "schedules"
    schedules.mkdir(parents=True)
    (schedules / "default.yaml").write_text(MANIFEST_TEXT, encoding="utf-8")
    workspace = ProjectWorkspace(tmp_path, schedules, tmp_path / "config.yaml", tmp_path / "marker.toml", None)
    state_root = tmp_path / "state"
    return InvocationContext(
        options=XcronOptions.create(tmp_path, backend="cron", state_root=state_root, crontab_path=tmp_path / "crontab"),
        workspace=workspace,
        settings=Settings(state_root=state_root, crontab_path=tmp_path / "crontab"),
    )


def test_jobs_manage_yaml_through_public_ports_without_scheduler_writes(tmp_path: Path) -> None:
    context = _context(tmp_path)
    crontab = context.options.crontab_path
    assert crontab is not None
    crontab.write_text("# externally owned\n", encoding="utf-8")
    host = CapabilityHost(CapabilityRegistry((WORKSPACE, MANIFEST, SCHEDULER, JOBS)))
    jobs = host.require("jobs", JobManagementPort)

    listed = jobs.list(ProjectRequest(), context)
    created = jobs.create(
        JobCreateRequest(job_id="cleanup", command="echo cleanup", schedule=ScheduleRequest.every("1h")),
        context,
    )
    updated = jobs.update(JobLookupRequest(job_identifier="cleanup"), JobUpdateRequest(command="echo newer"), context)
    disabled = jobs.disable(JobLookupRequest(job_identifier="cleanup"), context)
    shown = jobs.show(JobLookupRequest(job_identifier="cleanup"), context)
    removed = jobs.remove(JobLookupRequest(job_identifier="cleanup"), context)

    assert [job.job_id for job in listed.jobs] == ["archive"]
    assert created.job is not None and created.job.job_id == "cleanup"
    assert updated.job is not None and updated.job.execution.command == "echo newer"
    assert disabled.job is not None and disabled.job.enabled is False
    assert shown.raw_job == {"id": "cleanup", "command": "echo newer", "schedule": {"every": "1h"}, "enabled": False}
    assert removed.removed_job_identifier == "cleanup"
    assert crontab.read_text(encoding="utf-8") == "# externally owned\n"
    assert not (tmp_path / "state").exists()
    assert host.freeze().ids() == ("manifest:yaml", "workspace:local", "scheduler:native", "jobs:manifest")

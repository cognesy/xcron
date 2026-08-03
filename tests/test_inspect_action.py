from __future__ import annotations

import textwrap

from xcron_libs.actions.inspect_job import inspect_job
from xcron_libs.actions.validate_project import validate_project
from xcron_libs.capabilities.reconciliation.api import SchedulerRegistry
from xcron_libs.capabilities.reconciliation.contracts import SchedulerInspection
from xcron_libs.domain import ProjectState, StatusKind


def test_inspect_job_builds_launchd_raw_detail_sections(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: inspect-launchd
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: ping_job
                description: Ping from launchd
                schedule:
                  cron: "0 * * * *"
                command: echo ping
            """
        ),
        encoding="utf-8",
    )

    validation = validate_project(project)
    assert validation.valid is True
    assert validation.normalized_manifest is not None
    assert validation.hashes is not None

    inspection = SchedulerInspection(
        qualified_id="inspect-launchd.ping_job",
        job_id="ping_job",
        label="com.xcron.inspect-launchd.ping_job",
        artifact_path=str(tmp_path / "LaunchAgents" / "com.xcron.inspect-launchd.ping_job.plist"),
        wrapper_path=tmp_path / "state-root" / "projects" / "inspect-launchd" / "wrappers" / "inspect-launchd.ping_job.sh",
        desired_hash="desired-hash",
        definition_hash="definition-hash",
        enabled=True,
        loaded=True,
        raw_plist={
            "Label": "com.xcron.inspect-launchd.ping_job",
            "ProgramArguments": ["/tmp/wrapper.sh"],
        },
        launchctl_print="service = {\n\tstate = running\n}",
    )

    class LaunchdInspectionBackend:
        """Reports nothing deployed, so every desired job stays MISSING."""

        name = "launchd"

        def collect_project_state(self, project_id, **kwargs):
            return ProjectState(project_id=project_id, backend="launchd", manifest_hash=None)

        def inspect_project(self, *args, **kwargs):
            return (inspection,)

        def schedule_errors(self, jobs):
            return tuple()

    registry = SchedulerRegistry((LaunchdInspectionBackend(),))

    result = inspect_job(
        "ping_job",
        project,
        backend="launchd",
        scheduler_registry=registry,
    )

    assert result.valid is True
    assert result.status_entry is not None
    assert result.status_entry.kind is StatusKind.MISSING
    assert ("command", "echo ping") in {(field.name, field.value) for field in result.desired_fields}
    assert ("description", "Ping from launchd") in {(field.name, field.value) for field in result.desired_fields}
    assert ("label", "com.xcron.inspect-launchd.ping_job") in {(field.name, field.value) for field in result.deployed_fields}
    snippets = {snippet.name: snippet.content for snippet in result.snippets}
    assert "raw_plist" in snippets
    assert "<key>Label</key>" in snippets["raw_plist"]
    assert "launchctl_print" in snippets
    assert "state = running" in snippets["launchctl_print"]

from __future__ import annotations

import importlib
import textwrap

from libs.actions.inspect_job import inspect_job
from libs.actions.status_project import StatusProjectResult
from libs.actions.validate_project import validate_project
from libs.domain import ProjectState, StatusKind, build_project_plan, build_status_entries
from libs.services.backends.launchd_service import LaunchdInspection


def test_inspect_job_builds_launchd_raw_detail_sections(tmp_path, monkeypatch) -> None:
    inspect_job_module = importlib.import_module("libs.actions.inspect_job")
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

    plan = build_project_plan(
        validation.normalized_manifest,
        "launchd",
        validation.hashes.manifest_hash,
        validation.hashes.job_hashes,
        validation.hashes.job_definition_hashes,
        ProjectState(project_id="inspect-launchd", backend="launchd", manifest_hash=None),
    )
    status_result = StatusProjectResult(
        valid=True,
        backend="launchd",
        validation=validation,
        plan=plan,
        statuses=build_status_entries(plan),
        inspections=tuple(),
    )
    inspection = LaunchdInspection(
        qualified_id="inspect-launchd.ping_job",
        job_id="ping_job",
        label="com.xcron.inspect-launchd.ping_job",
        plist_path=tmp_path / "LaunchAgents" / "com.xcron.inspect-launchd.ping_job.plist",
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

    monkeypatch.setattr(inspect_job_module, "status_project", lambda *args, **kwargs: status_result)
    monkeypatch.setattr(inspect_job_module, "inspect_launchd_project", lambda *args, **kwargs: (inspection,))

    result = inspect_job("ping_job", project, backend="launchd")

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

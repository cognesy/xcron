from __future__ import annotations

import plistlib
import subprocess
import textwrap

from libs.actions.validate_project import validate_project
from libs.services.backends.launchd_service import collect_launchd_project_state, render_launchd_job, write_launchd_job


def test_launchd_backend_renders_managed_plist(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: launchd-demo
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: ping
                schedule:
                  cron: "0 * * * *"
                command: echo ping
            """
        ),
        encoding="utf-8",
    )

    validation = validate_project(project)
    assert validation.hashes is not None
    assert validation.normalized_manifest is not None
    job = validation.normalized_manifest.jobs[0]
    rendered = render_launchd_job(
        job,
        validation.hashes.job_hashes[job.qualified_id],
        validation.hashes.job_definition_hashes[job.qualified_id],
        state_root=tmp_path / "state-root",
        launch_agents_dir=tmp_path / "LaunchAgents",
    )
    plist_data = plistlib.loads(rendered.plist_content)

    assert plist_data["Label"] == "com.xcron.launchd-demo.ping"
    assert plist_data["ProgramArguments"] == [str(rendered.wrapper.runtime_paths.wrapper_path)]
    assert plist_data["EnvironmentVariables"]["XCRON_QUALIFIED_ID"] == "launchd-demo.ping"
    assert plist_data["StartCalendarInterval"] == {"Minute": 0}


def test_launchd_collect_state_preserves_job_id_for_dotted_project_id(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: demo.project
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: ping_job
                schedule:
                  cron: "0 * * * *"
                command: echo ping
            """
        ),
        encoding="utf-8",
    )

    validation = validate_project(project)
    assert validation.hashes is not None
    assert validation.normalized_manifest is not None
    job = validation.normalized_manifest.jobs[0]
    rendered = render_launchd_job(
        job,
        validation.hashes.job_hashes[job.qualified_id],
        validation.hashes.job_definition_hashes[job.qualified_id],
        state_root=tmp_path / "state-root",
        launch_agents_dir=tmp_path / "LaunchAgents",
    )
    write_launchd_job(rendered)

    state = collect_launchd_project_state(
        "demo.project",
        launch_agents_dir=tmp_path / "LaunchAgents",
        domain_target=f"gui/{subprocess.check_output(['id', '-u'], text=True).strip()}",
    )

    assert len(state.jobs) == 1
    assert state.jobs[0].job_id == "ping_job"
    assert state.jobs[0].stdout_log_path is not None
    assert state.jobs[0].stderr_log_path is not None
    assert state.jobs[0].stdout_log_path.endswith("demo.project.ping_job.out.log")
    assert state.jobs[0].stderr_log_path.endswith("demo.project.ping_job.err.log")

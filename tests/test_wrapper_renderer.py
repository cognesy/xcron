from __future__ import annotations

import json
import subprocess
import textwrap
import time

from libs.actions.validate_project import validate_project
from libs.services.wrapper_renderer import render_wrapper, write_wrapper


def test_wrapper_overlap_forbid_skips_and_cleans_lock(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XCRON_HOME", str(tmp_path / "xcron-home"))
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: demo-app
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: overlap_job
                schedule:
                  cron: "* * * * *"
                command: sleep 1; echo overlap-finished
                overlap: forbid
            """
        ),
        encoding="utf-8",
    )

    validation = validate_project(project)
    assert validation.hashes is not None
    assert validation.normalized_manifest is not None
    job = validation.normalized_manifest.jobs[0]
    rendered = render_wrapper(job, validation.hashes.job_hashes[job.qualified_id], state_root=tmp_path / "state-root")
    wrapper_path = write_wrapper(rendered)

    first = subprocess.Popen([str(wrapper_path)])
    time.sleep(0.1)
    second = subprocess.run([str(wrapper_path)], check=False)
    first.wait(timeout=5)

    stdout_text = rendered.runtime_paths.stdout_log_path.read_text(encoding="utf-8")
    stderr_text = rendered.runtime_paths.stderr_log_path.read_text(encoding="utf-8")
    event_payloads = [
        json.loads(line)
        for line in rendered.runtime_paths.event_log_path.read_text(encoding="utf-8").splitlines()
    ]

    assert second.returncode == 0
    assert "overlap-finished" in stdout_text
    assert "skipped overlapping run" in stderr_text
    assert "event=job_started" in stderr_text
    assert "event=job_finished" in stderr_text
    assert "xcron_metric ticks.started" in rendered.content
    assert "exit_code=0" in stderr_text
    assert "run_id=" in stderr_text
    assert [item["event"] for item in event_payloads] == [
        "job_started",
        "child_output",
        "job_finished",
    ]
    assert all(item["timestamp"].endswith("Z") for item in event_payloads)
    assert len({item["run_id"] for item in event_payloads}) == 1
    assert event_payloads[1]["stream"] == "stdout"
    assert event_payloads[1]["sequence"] == 0
    assert event_payloads[1]["line"] == "overlap-finished"
    assert event_payloads[-1]["exit_code"] == 0
    assert event_payloads[-1]["duration_seconds"] >= 1
    assert not rendered.runtime_paths.lock_path.exists()


def test_wrapper_records_nonzero_child_output_and_exit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XCRON_HOME", str(tmp_path / "xcron-home"))
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            """\
            version: 1
            project:
              id: demo-app
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: failing_job
                schedule:
                  cron: "* * * * *"
                command: printf 'child-out\\n'; printf 'child-err\\n' >&2; exit 7
            """
        ),
        encoding="utf-8",
    )

    validation = validate_project(project)
    assert validation.hashes is not None
    assert validation.normalized_manifest is not None
    job = validation.normalized_manifest.jobs[0]
    rendered = render_wrapper(job, validation.hashes.job_hashes[job.qualified_id], state_root=tmp_path / "state-root")
    wrapper_path = write_wrapper(rendered)

    result = subprocess.run([str(wrapper_path)], check=False)

    stdout_text = rendered.runtime_paths.stdout_log_path.read_text(encoding="utf-8")
    stderr_text = rendered.runtime_paths.stderr_log_path.read_text(encoding="utf-8")
    event_payloads = [
        json.loads(line)
        for line in rendered.runtime_paths.event_log_path.read_text(encoding="utf-8").splitlines()
    ]

    assert result.returncode == 7
    assert "child-out" in stdout_text
    assert "child-err" in stderr_text
    assert [(item["event"], item.get("stream"), item.get("line")) for item in event_payloads] == [
        ("job_started", None, None),
        ("child_output", "stdout", "child-out"),
        ("child_output", "stderr", "child-err"),
        ("job_finished", None, None),
    ]
    assert event_payloads[-1]["exit_code"] == 7

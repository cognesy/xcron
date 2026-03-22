from __future__ import annotations

import subprocess
import textwrap
import time

from libs.actions.validate_project import validate_project
from libs.services.wrapper_renderer import render_wrapper, write_wrapper


def test_wrapper_overlap_forbid_skips_and_cleans_lock(tmp_path) -> None:
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

    assert second.returncode == 0
    assert "overlap-finished" in stdout_text
    assert "skipped overlapping run" in stderr_text
    assert "event=job_started" in stderr_text
    assert "event=job_finished" in stderr_text
    assert "exit_code=0" in stderr_text
    assert not rendered.runtime_paths.lock_path.exists()

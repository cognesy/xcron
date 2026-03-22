from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap
import time

import pytest


if os.environ.get("XCRON_RUN_LAUNCHD_IT") != "1":
    pytest.skip("launchd integration test only runs when XCRON_RUN_LAUNCHD_IT=1", allow_module_level=True)


ROOT = Path(__file__).resolve().parents[2]


def run_xcron(project: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run one real xcron CLI command under uv for integration testing."""
    return subprocess.run(
        ["uv", "run", "xcron", "--project", str(project), "--backend", "launchd", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def wait_for_file(path: Path, *, contains: str | None = None, timeout: float = 10.0) -> str:
    """Wait until a file exists and optionally contains one marker."""
    deadline = time.time() + timeout
    last_text = ""
    while time.time() < deadline:
        if path.exists():
            last_text = path.read_text(encoding="utf-8")
            if contains is None or contains in last_text:
                return last_text
        time.sleep(0.25)
    raise AssertionError(f"timed out waiting for {path} to contain {contains!r}; last text was: {last_text!r}")


def test_launchd_real_apply_kickstart_and_prune(tmp_path: Path) -> None:
    uid = subprocess.check_output(["id", "-u"], text=True).strip()
    project_id = f"launchdit{os.getpid()}"
    project = tmp_path / "project"
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(
            f"""\
            version: 1
            project:
              id: {project_id}
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: ping
                schedule:
                  cron: "0 0 1 1 *"
                command: printf 'launchd-it-ok\\n'
            """
        ),
        encoding="utf-8",
    )

    state_root = tmp_path / "state-root"
    launch_agents_dir = tmp_path / "LaunchAgents"
    domain = f"gui/{uid}"
    label = f"com.xcron.{project_id}.ping"
    stdout_log = state_root / "projects" / project_id / "logs" / f"{project_id}.ping.out.log"
    stderr_log = state_root / "projects" / project_id / "logs" / f"{project_id}.ping.err.log"

    env = os.environ.copy()
    env.update(
        {
            "XCRON_RUN_LAUNCHD_IT": "1",
            "XCRON_STATE_ROOT": str(state_root),
            "XCRON_LAUNCH_AGENTS_DIR": str(launch_agents_dir),
            "XCRON_LAUNCHCTL_DOMAIN": domain,
            "XCRON_LOG_FORMAT": "json",
            "XCRON_LOG_LEVEL": "INFO",
        }
    )

    try:
        apply_result = run_xcron(project, "apply", env=env)
        assert apply_result.returncode == 0, apply_result.stderr
        assert '"event": "action_started"' in apply_result.stderr
        assert '"event": "action_finished"' in apply_result.stderr
        assert '"process_event": "launchd_bootstrap"' in apply_result.stderr
        assert "backend: launchd" in apply_result.stdout

        status_result = run_xcron(project, "status", env=env)
        assert status_result.returncode == 0, status_result.stderr
        assert "backend: launchd" in status_result.stdout

        inspect_result = run_xcron(project, "inspect", "ping", env=env)
        assert inspect_result.returncode == 0, inspect_result.stderr
        assert "loaded: True" in inspect_result.stdout
        assert f"wrapper_path: {state_root / 'projects' / project_id / 'wrappers' / f'{project_id}.ping.sh'}" in inspect_result.stdout
        assert f"stdout_log: {stdout_log}" in inspect_result.stdout
        assert f"stderr_log: {stderr_log}" in inspect_result.stdout

        kickstart = subprocess.run(
            ["launchctl", "kickstart", "-k", f"{domain}/{label}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert kickstart.returncode == 0, kickstart.stderr

        stdout_text = wait_for_file(stdout_log, contains="launchd-it-ok")
        stderr_text = wait_for_file(stderr_log, contains="event=job_finished")

        assert "launchd-it-ok" in stdout_text
        assert "event=job_started" in stderr_text
        assert "event=job_finished" in stderr_text
        assert "exit_code=0" in stderr_text

        prune_result = run_xcron(project, "prune", env=env)
        assert prune_result.returncode == 0, prune_result.stderr
        assert "removed: 1" in prune_result.stdout
    finally:
        subprocess.run(
            ["launchctl", "bootout", f"{domain}/{label}"],
            capture_output=True,
            text=True,
            check=False,
        )

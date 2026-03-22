from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import time


ROOT = Path(__file__).resolve().parents[2]


def run_xcron(project: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run one real xcron CLI command under uv for cron integration testing."""
    return subprocess.run(
        ["uv", "run", "xcron", "--project", str(project), "--backend", "cron", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def read_crontab() -> str:
    """Return the current container crontab content for the active user."""
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        if "no crontab" in result.stderr.lower():
            return ""
        raise AssertionError(f"failed to read crontab:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result.stdout


def require_ok(result: subprocess.CompletedProcess[str], step: str) -> None:
    """Raise with full command output when one CLI step fails."""
    if result.returncode == 0:
        return
    raise AssertionError(
        f"{step} failed with exit code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def wait_for_file(path: Path, *, contains: str, timeout: float = 95.0) -> str:
    """Wait until a file exists and contains one expected marker."""
    deadline = time.time() + timeout
    last_text = ""
    while time.time() < deadline:
        if path.exists():
            last_text = path.read_text(encoding="utf-8")
            if contains in last_text:
                return last_text
        time.sleep(1.0)
    sibling_listing = []
    if path.parent.exists():
        sibling_listing = sorted(item.name for item in path.parent.iterdir())
    raise AssertionError(
        f"timed out waiting for {path} to contain {contains!r}; "
        f"last text was {last_text!r}; sibling files: {sibling_listing}"
    )


def main() -> None:
    project_id = f"cronit{int(time.time())}"
    with tempfile.TemporaryDirectory(prefix="xcron-cron-it-") as temp_dir:
        root = Path(temp_dir)
        project = root / "project"
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
                      cron: "* * * * *"
                    command: printf 'cron-it-ok\\n'
                """
            ),
            encoding="utf-8",
        )

        state_root = root / "state-root"
        stdout_log = state_root / "projects" / project_id / "logs" / f"{project_id}.ping.out.log"
        stderr_log = state_root / "projects" / project_id / "logs" / f"{project_id}.ping.err.log"
        wrapper_path = state_root / "projects" / project_id / "wrappers" / f"{project_id}.ping.sh"

        env = os.environ.copy()
        env.update(
            {
                "XCRON_STATE_ROOT": str(state_root),
                "XCRON_LOG_FORMAT": "json",
                "XCRON_LOG_LEVEL": "INFO",
            }
        )

        apply_result = run_xcron(project, "apply", env=env)
        require_ok(apply_result, "xcron apply")
        assert "backend: cron" in apply_result.stdout
        assert '"event": "action_started"' in apply_result.stderr
        assert '"event": "action_finished"' in apply_result.stderr
        assert '"process_event": "cron_write_crontab"' in apply_result.stderr
        assert wrapper_path.exists(), f"expected wrapper to exist at {wrapper_path}"

        installed_crontab = read_crontab()
        assert f"# BEGIN XCRON project={project_id} backend=cron" in installed_crontab
        assert str(wrapper_path) in installed_crontab

        cron_process = subprocess.Popen(
            ["cron", "-f"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            time.sleep(1.0)
            if cron_process.poll() is not None:
                daemon_output = cron_process.stdout.read() if cron_process.stdout is not None else ""
                raise AssertionError(f"cron daemon exited early:\n{daemon_output}")

            status_result = run_xcron(project, "status", env=env)
            require_ok(status_result, "xcron status")
            assert "backend: cron" in status_result.stdout
            assert f"ok       {project_id}.ping" in status_result.stdout

            inspect_result = run_xcron(project, "inspect", "ping", env=env)
            require_ok(inspect_result, "xcron inspect ping")
            assert "backend: cron" in inspect_result.stdout
            assert f"desired: {project_id}.ping" in inspect_result.stdout
            assert f"artifact_path: <user crontab>" in inspect_result.stdout
            assert f"wrapper_path: {wrapper_path}" in inspect_result.stdout
            assert f"stdout_log: {stdout_log}" in inspect_result.stdout
            assert f"stderr_log: {stderr_log}" in inspect_result.stdout

            stdout_text = wait_for_file(stdout_log, contains="cron-it-ok")
            stderr_text = wait_for_file(stderr_log, contains="event=job_finished")
            assert "cron-it-ok" in stdout_text
            assert "event=job_started" in stderr_text
            assert "event=job_finished" in stderr_text
            assert "exit_code=0" in stderr_text

            prune_result = run_xcron(project, "prune", env=env)
            require_ok(prune_result, "xcron prune")
            assert "backend: cron" in prune_result.stdout
            assert "removed: 1" in prune_result.stdout

            pruned_crontab = read_crontab()
            assert project_id not in pruned_crontab
            assert not wrapper_path.exists(), f"expected wrapper to be pruned at {wrapper_path}"
        finally:
            if cron_process.poll() is None:
                cron_process.terminate()
                try:
                    cron_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    cron_process.kill()
                    cron_process.wait(timeout=5)


if __name__ == "__main__":
    main()

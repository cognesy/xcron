"""The drills named in the plane map, one test per row.

A degraded-behaviour table is a set of claims about what happens when something
is broken, and claims of that shape rot faster than anything else in a design
document: nothing exercises them, so nothing notices when they stop being true.
This lane is the executable half of that table. Each test is named after the
failure it drills, and `docs/dev/architecture.md` points here.

The first row is the one that justifies xcron's whole design — deployed jobs
keep firing when xcron is gone — and it is drilled by actually running a
deployed wrapper in a subprocess that cannot see xcron at all.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from xcron.sdk.client import Xcron

BACKEND = "cron"

MANIFEST = textwrap.dedent(
    """\
    version: 1
    project:
      id: degraded-demo
    defaults:
      working_dir: .
      shell: /bin/sh
    jobs:
      - id: heartbeat
        schedule:
          cron: "*/5 * * * *"
        command: echo still-firing
    """
)


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real project reconciled against a file crontab, never the host."""
    root = tmp_path / "project"
    (root / "resources" / "schedules").mkdir(parents=True)
    (root / "resources" / "schedules" / "default.yaml").write_text(MANIFEST, encoding="utf-8")

    monkeypatch.setenv("XCRON_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XCRON_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("XCRON_CRONTAB_PATH", str(tmp_path / "crontab"))
    monkeypatch.setenv("XCRON_MANAGE_CRONTAB", "1")
    monkeypatch.setenv("XCRON_MANAGE_LAUNCHCTL", "0")
    return root


def _state_file(tmp_path: Path) -> Path:
    return tmp_path / "state" / "projects" / "degraded-demo" / "project-state.json"


def _apply(project: Path):
    with Xcron.open(project, backend=BACKEND) as client:
        return client.schedules.apply()


# --- Row 1: xcron not installed or broken -----------------------------------


def test_a_deployed_job_still_runs_when_xcron_is_not_there(
    project: Path, tmp_path: Path
) -> None:
    """The availability property, drilled rather than asserted in prose.

    The wrapper is executed by a shell with an environment that contains no
    xcron: an empty `PYTHONPATH`, a `PATH` holding only the system directories,
    and `sys.executable`'s directory removed. If the wrapper needed xcron to
    run, this is where it would fail.
    """
    applied = _apply(project)
    assert applied.applied_state is not None and applied.applied_state.jobs

    deployed = applied.applied_state.jobs[0]
    wrapper = Path(deployed.wrapper_path)
    assert wrapper.is_file()

    stripped = {
        "HOME": str(tmp_path / "fake-home"),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONPATH": "",
    }
    completed = subprocess.run(
        ["/bin/sh", str(wrapper)], env=stripped, capture_output=True, text=True, timeout=60
    )

    assert completed.returncode == 0, completed.stderr
    stdout_log = Path(deployed.stdout_log_path)
    assert "still-firing" in stdout_log.read_text(encoding="utf-8")


def test_the_deployed_artifacts_never_call_back_into_xcron(project: Path) -> None:
    """Why the drill above can pass: nothing deployed invokes the tool.

    A wrapper that shelled out to `xcron` would convert a management-plane
    outage into a data-plane outage, which is exactly the coupling the design
    refuses. `xcron_` prefixes name the wrapper's own shell functions, so the
    check is on invocations, not on the string.
    """
    applied = _apply(project)
    assert applied.applied_state is not None
    wrapper_text = Path(applied.applied_state.jobs[0].wrapper_path).read_text(encoding="utf-8")

    for line in wrapper_text.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("xcron "), line
        assert "import xcron" not in stripped, line

    crontab = Path(os.environ["XCRON_CRONTAB_PATH"]).read_text(encoding="utf-8")
    for line in crontab.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        assert " xcron " not in f" {line} ", line


# --- Row 2: project-state.json missing or stale ------------------------------


def test_losing_derived_state_degrades_visibly_not_silently(
    project: Path, tmp_path: Path
) -> None:
    """`plan` reports creates it cannot know are redundant; `status` still knows.

    That asymmetry is the design: `plan` reads the record, `status` asks the
    scheduler. Losing the record must never look like "nothing to do".
    """
    _apply(project)
    state_file = _state_file(tmp_path)
    assert state_file.is_file()
    state_file.unlink()

    with Xcron.open(project, backend=BACKEND) as client:
        plan = client.schedules.plan()
        status = client.schedules.status()

    assert [change.kind.value for change in plan.changes] == ["create"]
    assert [entry.kind.value for entry in status.statuses] == ["ok"], status.statuses


def test_a_corrupt_state_document_does_not_take_the_project_down(
    project: Path, tmp_path: Path
) -> None:
    _apply(project)
    _state_file(tmp_path).write_text("{ not json", encoding="utf-8")

    with Xcron.open(project, backend=BACKEND) as client:
        assert client.schedules.status().statuses


# --- Row 3: host scheduler unavailable ---------------------------------------


def test_a_failing_scheduler_write_leaves_the_durable_record_untouched(
    project: Path, tmp_path: Path
) -> None:
    """No half-converged record: the state file is written after the scheduler.

    The scheduler is made genuinely unavailable — the crontab is read-only —
    rather than monkeypatched, so this drills the same path a failing
    `crontab -` would take. Wrapper scripts *are* on disk by then: they are
    rendered to compute the entries that reference them. Nothing schedules
    them, so they are inert, and the next successful `apply` overwrites them.
    """
    if os.geteuid() == 0:
        pytest.skip("root ignores the mode bits this drill relies on")

    first = _apply(project)
    before = _state_file(tmp_path).read_text(encoding="utf-8")

    crontab = Path(os.environ["XCRON_CRONTAB_PATH"])
    crontab_before = crontab.read_text(encoding="utf-8")
    crontab.chmod(0o400)

    (project / "resources" / "schedules" / "default.yaml").write_text(
        MANIFEST.replace("echo still-firing", "echo changed"), encoding="utf-8"
    )
    try:
        with pytest.raises(OSError):
            _apply(project)
    finally:
        crontab.chmod(0o600)

    assert crontab.read_text(encoding="utf-8") == crontab_before
    assert _state_file(tmp_path).read_text(encoding="utf-8") == before
    assert first.applied_state is not None
    assert json.loads(before)["manifest_hash"] == first.applied_state.manifest_hash


# --- Row 6: metrics store unreadable -----------------------------------------


def test_a_corrupt_metrics_store_never_blocks_an_action(
    project: Path, tmp_path: Path
) -> None:
    """Counters are an operator convenience; nothing may depend on reading them.

    The store does better than the plane map's "reports empty rather than
    failing": unreadable content is discarded and the file heals on the next
    write. What must never happen is an action failing because of it.
    """
    metrics_path = tmp_path / "home" / "metrics" / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text("<<< not json >>>", encoding="utf-8")

    with Xcron.open(project, backend=BACKEND) as client:
        assert client.operations.show_metrics().counters == {}

    applied = _apply(project)
    assert applied.applied_state is not None and applied.applied_state.jobs

    with Xcron.open(project, backend=BACKEND) as client:
        healed = client.operations.show_metrics()
    assert healed.counters["apply.succeeded"] == 1
    assert json.loads(metrics_path.read_text(encoding="utf-8"))["version"] == 1


def test_a_metrics_directory_that_cannot_be_written_never_blocks_an_action(
    project: Path, tmp_path: Path
) -> None:
    """The store swallows write failures; `apply` must not learn about them."""
    if os.geteuid() == 0:
        pytest.skip("root ignores the mode bits this drill relies on")

    metrics_dir = tmp_path / "home" / "metrics"
    metrics_dir.mkdir(parents=True)
    metrics_dir.chmod(0o500)
    try:
        applied = _apply(project)
        assert applied.applied_state is not None and applied.applied_state.jobs
    finally:
        metrics_dir.chmod(0o700)


# --- Row 5 lives with the module that owns the marker ------------------------


def test_the_marker_drills_are_owned_by_the_workspace_module() -> None:
    """A pointer, so the table's fifth row is not read as undrilled.

    `workspace` owns the marker, so the drills for it belong to that module's
    lane rather than here. This test fails if that file is renamed away.
    """
    lane = Path(__file__).resolve().parents[1] / "modules" / "workspace" / "test_marker.py"
    source = lane.read_text(encoding="utf-8")

    assert "def test_an_unmarked_workspace_warns_and_proceeds" in source
    assert "def test_an_untrustworthy_marker_stops_resolution_outright" in source


def test_the_drill_environment_really_is_the_one_being_measured() -> None:
    """A self-check: `sys.executable` must not be reachable through the stripped PATH.

    If the test runner happened to live in `/usr/bin`, the row 1 drill would be
    proving nothing.
    """
    system_directories = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
    interpreter_directory = str(Path(sys.executable).parent)

    assert interpreter_directory not in system_directories, (
        "the row 1 drill needs an interpreter outside the system PATH to be meaningful"
    )

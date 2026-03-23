from __future__ import annotations

import plistlib
import subprocess
import textwrap

import pytest

from libs.actions.validate_project import validate_project
from libs.services.backends.launchd_service import (
    collect_launchd_project_state,
    parse_calendar_field,
    render_launchd_job,
    render_launchd_schedule,
    write_launchd_job,
)


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


# ---------------------------------------------------------------------------
# parse_calendar_field unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,field_name,expected", [
    ("*",        "Minute",  None),
    ("0",        "Minute",  [0]),
    ("30",       "Minute",  [30]),
    ("0,30",     "Minute",  [0, 30]),
    ("0,15,30,45", "Minute", [0, 15, 30, 45]),
    ("9-17",     "Hour",    list(range(9, 18))),
    ("1-5",      "Weekday", [1, 2, 3, 4, 5]),
    ("*/4",      "Hour",    [0, 4, 8, 12, 16, 20]),
    ("*/5",      "Day",     [1, 6, 11, 16, 21, 26, 31]),
    ("*/15",     "Minute",  [0, 15, 30, 45]),
    ("8-20/4",   "Hour",    [8, 12, 16, 20]),
    ("0,8-20/4", "Hour",    [0, 8, 12, 16, 20]),
    ("6/2",      "Hour",    list(range(6, 24, 2))),
    ("0-6",      "Weekday", [0, 1, 2, 3, 4, 5, 6]),
])
def test_parse_calendar_field(field, field_name, expected) -> None:
    assert parse_calendar_field(field, field_name) == expected


# ---------------------------------------------------------------------------
# render_launchd_schedule integration tests
# ---------------------------------------------------------------------------

def _make_job_for_cron(tmp_path, cron_expr: str):
    """Return a NormalizedJob for a single-job project with the given cron expression."""
    project = tmp_path / "project"
    project.mkdir()
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        textwrap.dedent(f"""\
            version: 1
            project:
              id: test-launchd
            defaults:
              working_dir: .
              shell: /bin/sh
            jobs:
              - id: job
                schedule:
                  cron: "{cron_expr}"
                command: echo test
            """),
        encoding="utf-8",
    )
    validation = validate_project(project)
    assert validation.normalized_manifest is not None
    return validation.normalized_manifest.jobs[0]


@pytest.mark.parametrize("cron_expr,key,expected_value", [
    # Minute-only step → StartInterval (optimization preserved)
    ("*/15 * * * *", "StartInterval", 900),
    ("*/1 * * * *",  "StartInterval", 60),
    # Hourly at :00 → single-entry StartCalendarInterval
    ("0 * * * *",    "StartCalendarInterval", {"Minute": 0}),
    # Every 4 hours at :00
    ("0 */4 * * *",  "StartCalendarInterval", [
        {"Hour": h, "Minute": 0} for h in [0, 4, 8, 12, 16, 20]
    ]),
    # Every 2 days at 00:00
    ("0 0 */2 * *",  "StartCalendarInterval", [
        {"Day": d, "Hour": 0, "Minute": 0} for d in [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31]
    ]),
    # At :00 and :30 every hour
    ("0,30 * * * *", "StartCalendarInterval", [{"Minute": 0}, {"Minute": 30}]),
    # Weekdays at midnight
    ("0 0 * * 1-5",  "StartCalendarInterval", [
        {"Hour": 0, "Minute": 0, "Weekday": w} for w in [1, 2, 3, 4, 5]
    ]),
    # 9am–5pm on weekdays at :00 (9 hours × 5 days = 45 entries)
    ("0 9-17 * * 1-5", "StartCalendarInterval", [
        {"Hour": h, "Minute": 0, "Weekday": w}
        for h in range(9, 18) for w in range(1, 6)
    ]),
    # Step + range: every 4 hours within 8–20
    ("0 8-20/4 * * *", "StartCalendarInterval", [
        {"Hour": h, "Minute": 0} for h in [8, 12, 16, 20]
    ]),
])
def test_render_launchd_schedule_patterns(tmp_path, cron_expr, key, expected_value) -> None:
    job = _make_job_for_cron(tmp_path, cron_expr)
    result = render_launchd_schedule(job)
    assert key in result, f"expected key {key!r} in {result}"
    actual = result[key]
    if isinstance(expected_value, list):
        assert sorted(actual, key=lambda d: sorted(d.items())) == sorted(
            expected_value, key=lambda d: sorted(d.items())
        ), f"StartCalendarInterval mismatch for {cron_expr!r}"
    else:
        assert actual == expected_value

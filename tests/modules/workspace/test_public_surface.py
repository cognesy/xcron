"""Workspace identity and layout, exercised through its public surface.

Every path xcron writes to is derived here. These tests pin the resolution
precedence and the derived layout so a later change to either is a deliberate
edit rather than an accident.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xcron.capabilities.workspace.api import (
    MANIFEST_DIR,
    ensure_runtime_dirs,
    resolve_manifest_dir,
    resolve_project_root,
    resolve_project_state_dir,
    resolve_runtime_paths,
    resolve_state_root,
    resolve_xcron_home,
    runtime_event_log_path_for_wrapper,
    runtime_log_paths_for_wrapper,
)
from xcron.capabilities.workspace.contracts import (
    UnsupportedPlatformError,
    WorkspaceResolutionError,
)
from xcron.domain.models import (
    NormalizedExecutionConfig,
    NormalizedJob,
    OverlapPolicy,
    ScheduleDefinition,
    ScheduleKind,
)


def _job(project_id: str = "demo", job_id: str = "alpha") -> NormalizedJob:
    return NormalizedJob(
        project_id=project_id,
        job_id=job_id,
        qualified_id=f"{project_id}.{job_id}",
        artifact_id=f"{project_id}.{job_id}",
        enabled=True,
        schedule=ScheduleDefinition(kind=ScheduleKind.CRON, value="0 * * * *"),
        execution=NormalizedExecutionConfig(
            command="echo hi",
            working_dir="/tmp",
            shell="/bin/sh",
            timezone=None,
            env=(),
            overlap=OverlapPolicy.ALLOW,
        ),
    )


def test_xcron_home_prefers_the_environment_override(tmp_path: Path) -> None:
    assert resolve_xcron_home(env={"XCRON_HOME": str(tmp_path)}) == tmp_path.resolve()
    assert resolve_xcron_home(env={}) == (Path.home() / ".xcron").resolve()


def test_an_explicit_project_path_wins_over_the_working_directory(tmp_path: Path) -> None:
    explicit = tmp_path / "explicit"
    (explicit / MANIFEST_DIR).mkdir(parents=True)

    assert resolve_project_root(explicit) == explicit.resolve()


def test_a_missing_or_non_directory_root_raises_the_typed_workspace_error(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceResolutionError, match="does not exist"):
        resolve_project_root(tmp_path / "absent")

    file_path = tmp_path / "a-file"
    file_path.write_text("", encoding="utf-8")
    with pytest.raises(WorkspaceResolutionError, match="not a directory"):
        resolve_project_root(file_path)


def test_the_legacy_schedules_location_still_resolves(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    (legacy / "resources" / "schedules").mkdir(parents=True)

    assert resolve_manifest_dir(legacy) == (legacy / "resources" / "schedules").resolve()


def test_the_state_root_honours_its_override_and_rejects_unknown_platforms(tmp_path: Path) -> None:
    """The override is a value, not an environment read; see `paths`."""
    assert resolve_state_root(override=str(tmp_path)) == tmp_path.resolve()
    assert resolve_state_root("darwin", home=tmp_path) == (tmp_path / ".xcron").resolve()

    with pytest.raises(UnsupportedPlatformError):
        resolve_state_root("win32", home=tmp_path)


def test_runtime_paths_are_derived_from_the_project_state_directory(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(_job(), state_root=tmp_path)
    project_dir = resolve_project_state_dir("demo", state_root=tmp_path)

    assert paths.project_dir == project_dir
    assert paths.wrapper_path == project_dir / "wrappers" / "demo.alpha.sh"
    assert paths.stdout_log_path == project_dir / "logs" / "demo.alpha.out.log"
    assert paths.event_log_path == project_dir / "logs" / "demo.alpha.events.jsonl"
    assert paths.lock_path == project_dir / "locks" / "demo.alpha.lock"


def test_log_paths_round_trip_from_a_wrapper_path_alone(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(_job(), state_root=tmp_path)
    ensure_runtime_dirs(paths)

    stdout_path, stderr_path = runtime_log_paths_for_wrapper(paths.wrapper_path)

    assert (stdout_path, stderr_path) == (paths.stdout_log_path, paths.stderr_log_path)
    assert runtime_event_log_path_for_wrapper(paths.wrapper_path) == paths.event_log_path
    assert paths.wrappers_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert paths.locks_dir.is_dir()

"""Workspace resolution precedence, one test per adjacent pair.

Precedence bugs are silent: xcron reads the wrong directory and reports
correctly about it. Each test below removes exactly one level and asserts the
next one takes over, so a reordering cannot pass by satisfying a weaker check.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xcron_libs.capabilities.workspace.api import (
    find_workspace_root,
    is_workspace,
    resolve_manifest_dir,
    resolve_project_root,
    resolve_workspace,
    write_marker,
)
from xcron_libs.capabilities.workspace.contracts import WorkspaceResolutionError


def _workspace(root: Path) -> Path:
    (root / "schedules").mkdir(parents=True)
    return root


def test_an_explicit_path_beats_the_environment(tmp_path: Path) -> None:
    explicit = _workspace(tmp_path / "explicit")
    from_env = _workspace(tmp_path / "from-env")

    resolved = resolve_project_root(explicit, env={"XCRON_PROJECT": str(from_env)})

    assert resolved == explicit.resolve()


def test_the_environment_beats_the_surrounding_directory(tmp_path: Path) -> None:
    from_env = _workspace(tmp_path / "from-env")
    nearby = _workspace(tmp_path / "nearby")

    resolved = resolve_project_root(env={"XCRON_PROJECT": str(from_env)}, start=nearby)

    assert resolved == from_env.resolve()


def test_the_surrounding_directory_beats_the_xcron_home(tmp_path: Path) -> None:
    nearby = _workspace(tmp_path / "nearby")
    home = _workspace(tmp_path / "home")

    resolved = resolve_project_root(env={"XCRON_HOME": str(home)}, start=nearby)

    assert resolved == nearby.resolve()


def test_the_nearest_enclosing_workspace_wins_over_a_further_one(tmp_path: Path) -> None:
    outer = _workspace(tmp_path / "outer")
    inner = _workspace(outer / "packages" / "inner")
    deep = inner / "src" / "lib"
    deep.mkdir(parents=True)

    assert find_workspace_root(deep) == inner.resolve()
    assert resolve_project_root(env={}, start=deep) == inner.resolve()


def test_a_directory_that_is_not_a_workspace_falls_through_to_the_home(tmp_path: Path) -> None:
    home = _workspace(tmp_path / "home")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    resolved = resolve_project_root(env={"XCRON_HOME": str(home)}, start=elsewhere)

    assert resolved == home.resolve()


def test_nothing_resolvable_raises_the_typed_error_with_a_recovery_hint(tmp_path: Path) -> None:
    absent = tmp_path / "no-home"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    with pytest.raises(WorkspaceResolutionError, match="xcron init"):
        resolve_project_root(env={"XCRON_HOME": str(absent)}, start=elsewhere)


def test_a_marker_alone_makes_a_directory_a_workspace(tmp_path: Path) -> None:
    """Marked-but-empty must count, or `init` could not create one bottom-up."""
    root = tmp_path / "marked"
    root.mkdir()
    write_marker(root, created_by="xcron test")

    assert is_workspace(root)
    assert find_workspace_root(root) == root.resolve()


def test_the_legacy_layout_still_counts_as_a_workspace(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    (root / "resources" / "schedules").mkdir(parents=True)

    assert is_workspace(root)
    assert resolve_manifest_dir(root) == (root / "resources" / "schedules").resolve()


def test_the_current_layout_wins_over_the_legacy_one(tmp_path: Path) -> None:
    root = _workspace(tmp_path / "both")
    (root / "resources" / "schedules").mkdir(parents=True)

    assert resolve_manifest_dir(root) == (root / "schedules").resolve()


def test_a_workspace_reports_its_own_config_and_manifest_locations(tmp_path: Path) -> None:
    root = _workspace(tmp_path / "project")

    resolved = resolve_workspace(root, on_missing_marker=lambda _root: None)

    assert resolved.manifest_dir == (root / "schedules").resolve()
    assert resolved.config_path == root.resolve() / "config.yaml"
    assert resolved.marker_path == (root / "marker.toml").resolve()


def test_two_workspaces_resolve_independently_in_one_process(tmp_path: Path) -> None:
    """Nothing about resolution is cached, so an embedder can hold both."""
    first = _workspace(tmp_path / "first")
    second = _workspace(tmp_path / "second")
    write_marker(second, created_by="xcron test")

    a = resolve_workspace(first, on_missing_marker=lambda _root: None)
    b = resolve_workspace(second)

    assert (a.root, a.is_marked) == (first.resolve(), False)
    assert (b.root, b.is_marked) == (second.resolve(), True)

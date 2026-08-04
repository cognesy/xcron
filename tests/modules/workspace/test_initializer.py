"""Init writes into a directory xcron does not yet own, so it stays timid.

The property worth protecting is that running init can never lose data. Every
test here either checks that something absent got created, or that something
present survived untouched and was reported rather than replaced.
"""

from __future__ import annotations

from pathlib import Path

from xcron_libs.capabilities.workspace.api import (
    initialize_workspace,
    marker_path,
    read_marker,
)


def test_a_fresh_directory_gets_a_manifest_and_a_marker(tmp_path: Path) -> None:
    home = tmp_path / "xcron-home"

    result = initialize_workspace(home, created_by="xcron test")

    assert result.created is True
    assert result.xcron_home == str(home)
    assert result.schedules_dir == str(home / "schedules")
    assert result.manifest_path == str(home / "schedules" / "default.yaml")
    assert result.marker_path == str(home / "marker.toml")
    assert set(result.created_paths) == {
        str(home / "schedules"),
        str(home / "schedules" / "default.yaml"),
        str(home / "marker.toml"),
    }
    assert result.retained_paths == ()
    assert result.conflicts == ()

    manifest = Path(result.manifest_path).read_text(encoding="utf-8")
    assert "my-schedules" in manifest
    assert "version: 1" in manifest
    assert read_marker(home).created_by == "xcron test"


def test_running_it_twice_changes_nothing_the_second_time(tmp_path: Path) -> None:
    home = tmp_path / "xcron-home"
    first = initialize_workspace(home, created_by="xcron test")
    assert first.created is True

    Path(first.manifest_path).write_text("custom content", encoding="utf-8")
    second = initialize_workspace(home, created_by="xcron test")

    assert second.created is False
    assert second.created_paths == ()
    assert Path(second.manifest_path).read_text(encoding="utf-8") == "custom content"
    assert set(second.retained_paths) == {
        str(home / "schedules"),
        str(home / "schedules" / "default.yaml"),
        str(home / "marker.toml"),
    }


def test_an_existing_workspace_gains_only_the_marker(tmp_path: Path) -> None:
    """The upgrade path: a pre-marker workspace is completed, not rebuilt."""
    home = tmp_path / "existing"
    (home / "schedules").mkdir(parents=True)
    (home / "schedules" / "default.yaml").write_text("version: 1\n", encoding="utf-8")

    result = initialize_workspace(home, created_by="xcron test")

    assert result.created is False
    assert result.created_paths == (str(home / "marker.toml"),)
    assert (home / "schedules" / "default.yaml").read_text(encoding="utf-8") == "version: 1\n"


def test_a_legacy_layout_is_adopted_where_it_stands(tmp_path: Path) -> None:
    home = tmp_path / "legacy"
    legacy = home / "resources" / "schedules"
    legacy.mkdir(parents=True)
    (legacy / "default.yaml").write_text("version: 1\n", encoding="utf-8")

    result = initialize_workspace(home, created_by="xcron test")

    assert result.migrated_paths == (str(legacy),)
    assert result.created is False
    assert not (home / "schedules").exists()
    assert (legacy / "default.yaml").read_text(encoding="utf-8") == "version: 1\n"
    assert marker_path(home).is_file()


def test_a_file_where_the_schedules_directory_belongs_is_a_reported_conflict(
    tmp_path: Path,
) -> None:
    home = tmp_path / "occupied"
    home.mkdir()
    (home / "schedules").write_text("not a directory", encoding="utf-8")

    result = initialize_workspace(home, created_by="xcron test")

    assert result.created is False
    assert len(result.conflicts) == 1
    assert "is not a directory" in result.conflicts[0]
    assert (home / "schedules").read_text(encoding="utf-8") == "not a directory"


def test_an_unreadable_marker_is_reported_and_left_alone(tmp_path: Path) -> None:
    home = tmp_path / "broken"
    (home / "schedules").mkdir(parents=True)
    marker_path(home).write_text("kind = = =", encoding="utf-8")

    result = initialize_workspace(home, created_by="xcron test")

    assert len(result.conflicts) == 1
    assert "unusable" in result.conflicts[0]
    assert marker_path(home).read_text(encoding="utf-8") == "kind = = ="


def test_an_existing_valid_marker_is_never_rewritten(tmp_path: Path) -> None:
    home = tmp_path / "marked"
    (home / "schedules").mkdir(parents=True)
    initialize_workspace(home, created_by="xcron original")

    result = initialize_workspace(home, created_by="xcron later")

    assert str(marker_path(home)) in result.retained_paths
    assert read_marker(home).created_by == "xcron original"

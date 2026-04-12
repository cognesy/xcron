"""Tests for the init_home action and xcron home resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from libs.actions.init_home import init_home
from libs.services.config_loader import (
    resolve_manifest_dir,
    resolve_project_root,
    resolve_xcron_home,
)


def test_resolve_xcron_home_defaults_to_dot_xcron() -> None:
    home = resolve_xcron_home(env={})
    assert home == (Path.home() / ".xcron").resolve()


def test_resolve_xcron_home_respects_env_override(tmp_path: Path) -> None:
    home = resolve_xcron_home(env={"XCRON_HOME": str(tmp_path / "custom")})
    assert home == (tmp_path / "custom").resolve()


def test_init_home_creates_schedules_dir_and_manifest(tmp_path: Path) -> None:
    xcron_home = tmp_path / "xcron-home"
    result = init_home(xcron_home=xcron_home)

    assert result.created is True
    assert result.xcron_home == str(xcron_home)
    assert result.schedules_dir == str(xcron_home / "schedules")
    assert result.manifest_path == str(xcron_home / "schedules" / "default.yaml")

    manifest = Path(result.manifest_path)
    assert manifest.exists()
    content = manifest.read_text()
    assert "my-schedules" in content
    assert "version: 1" in content


def test_init_home_does_not_overwrite_existing_manifest(tmp_path: Path) -> None:
    xcron_home = tmp_path / "xcron-home"
    first = init_home(xcron_home=xcron_home)
    assert first.created is True

    Path(first.manifest_path).write_text("custom content")

    second = init_home(xcron_home=xcron_home)
    assert second.created is False
    assert Path(second.manifest_path).read_text() == "custom content"


def test_resolve_manifest_dir_prefers_schedules_over_legacy(tmp_path: Path) -> None:
    (tmp_path / "schedules").mkdir()
    (tmp_path / "resources" / "schedules").mkdir(parents=True)

    result = resolve_manifest_dir(tmp_path)
    assert result == (tmp_path / "schedules").resolve()


def test_resolve_manifest_dir_falls_back_to_legacy(tmp_path: Path) -> None:
    (tmp_path / "resources" / "schedules").mkdir(parents=True)

    result = resolve_manifest_dir(tmp_path)
    assert result == (tmp_path / "resources" / "schedules").resolve()


def test_resolve_manifest_dir_returns_primary_when_neither_exists(tmp_path: Path) -> None:
    result = resolve_manifest_dir(tmp_path)
    assert result == (tmp_path / "schedules").resolve()


def test_resolve_project_root_uses_cwd_when_schedules_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "schedules").mkdir()
    monkeypatch.chdir(tmp_path)

    result = resolve_project_root()
    assert result == tmp_path.resolve()


def test_resolve_project_root_falls_back_to_xcron_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xcron_home = tmp_path / "xcron-home"
    xcron_home.mkdir()
    (tmp_path / "some-random-dir").mkdir()
    monkeypatch.setenv("XCRON_HOME", str(xcron_home))
    monkeypatch.chdir(tmp_path / "some-random-dir")

    result = resolve_project_root()
    assert result == xcron_home.resolve()


def test_resolve_project_root_uses_cwd_with_legacy_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "resources" / "schedules").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    result = resolve_project_root()
    assert result == tmp_path.resolve()

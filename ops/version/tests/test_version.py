from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
from types import ModuleType, SimpleNamespace
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "ops" / "version" / "bin" / "version.py"


def _versioning() -> ModuleType:
    spec = importlib.util.spec_from_file_location("xcron_ops_version", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _copied_repository(tmp_path: Path) -> Path:
    destination = tmp_path / "xcron"
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", ".venv", "dist", "build", "__pycache__", ".pytest_cache"),
    )
    return destination


def _refresh_copied_lock(root: Path) -> None:
    lock = root / "uv.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8").replace('version = "0.1.0"', 'version = "0.1.1"'),
        encoding="utf-8",
    )


def test_live_workspace_has_one_valid_lockstep_version() -> None:
    versioning = _versioning()

    assert versioning.release_version(ROOT) == "0.1.0"
    assert versioning.validate(ROOT) == []
    assert versioning.next_version(ROOT, "patch") == "0.1.1"
    assert versioning.next_version(ROOT, "minor") == "0.2.0"
    assert versioning.next_version(ROOT, "major") == "1.0.0"


def test_planned_update_covers_every_metadata_and_provider_projection() -> None:
    versioning = _versioning()

    updates = versioning.planned_updates(ROOT, "0.1.1")
    projects = versioning.workspace_projects(ROOT)
    provider_projects = [
        project for project in projects if versioning._provider_descriptors(project, ROOT)
    ]

    assert updates[ROOT / "ops/version/current.yaml"].count("product_version: 0.1.1") == 1
    assert all('version = "0.1.1"' in updates[project.path] for project in projects)
    assert len(provider_projects) == 10
    for project in provider_projects:
        descriptor = versioning._provider_descriptors(project, ROOT)[0]
        assert 'version="0.1.1"' in updates[descriptor.source]


def test_set_refreshes_lock_and_rolls_back_every_file_on_failure(tmp_path: Path) -> None:
    versioning = _versioning()
    repository = _copied_repository(tmp_path)

    versioning.set_version(repository, "0.1.1", lock_runner=_refresh_copied_lock)

    assert versioning.release_version(repository) == "0.1.1"
    assert versioning.validate(repository) == []

    before = (repository / "ops/version/current.yaml").read_text(encoding="utf-8")
    with pytest.raises(versioning.VersionError, match="lock failure"):
        versioning.set_version(
            repository,
            "0.1.2",
            lock_runner=lambda _: (_ for _ in ()).throw(versioning.VersionError("lock failure")),
        )
    assert (repository / "ops/version/current.yaml").read_text(encoding="utf-8") == before
    assert versioning.validate(repository) == []


def test_package_bundle_uses_wheel_metadata_and_hashes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    versioning = _versioning()

    def fake_build(command: list[str], **_: object) -> SimpleNamespace:
        destination = Path(command[command.index("--out-dir") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        for project in versioning.workspace_projects(ROOT):
            wheel = destination / f"{project.name.replace('-', '_')}-0.1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(
                    f"{project.name.replace('-', '_')}-0.1.0.dist-info/METADATA",
                    f"Metadata-Version: 2.1\nName: {project.name}\nVersion: 0.1.0\n",
                )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(versioning.subprocess, "run", fake_build)
    destination = tmp_path / "xcron-release"

    bundle = versioning.package_release(ROOT, str(destination))

    manifest = json.loads((destination / "release-manifest.json").read_text(encoding="utf-8"))
    checksums = (destination / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    assert bundle["productVersion"] == "0.1.0"
    assert {entry["distribution"] for entry in manifest["wheels"]} == {
        project.name for project in versioning.workspace_projects(ROOT)
    }
    assert len(checksums) == len(manifest["wheels"])
    assert all(re.fullmatch(r"[0-9a-f]{64}  .+\.whl", entry) for entry in checksums)


def test_package_refuses_to_clear_an_explicit_repository_path() -> None:
    versioning = _versioning()

    with pytest.raises(versioning.VersionError, match="outside the repository"):
        versioning._safe_output_directory(ROOT, str(ROOT / "release-artifacts"), "0.1.0")


def test_release_workflow_is_a_checked_packaging_projection(tmp_path: Path) -> None:
    versioning = _versioning()
    repository = _copied_repository(tmp_path)
    workflow = repository / ".github/workflows/release.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace("gh release upload", "release upload removed"),
        encoding="utf-8",
    )

    diagnostics = versioning.validate(repository)

    assert any(
        item.path == versioning.RELEASE_WORKFLOW and "gh release upload" in item.message
        for item in diagnostics
    )

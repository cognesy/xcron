"""The manifest module exercised only through `api` and `contracts`.

This lane is the caller's view. It proves that reading, validating, hashing,
and editing a manifest are all reachable from the public surface, so the four
private modules behind it can be rearranged without a caller change.
"""

from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from xcron_libs.capabilities.manifest.api import (
    add_manifest_job,
    build_manifest_hashes,
    load_project_manifest,
    load_schema,
    parse_project_manifest,
    resolve_manifest_path,
    split_validation_messages,
    validate_schema,
)
from xcron_libs.capabilities.manifest.contracts import (
    AmbiguousManifestSelectionError,
    ManifestJobAlreadyExistsError,
    ManifestNotFoundError,
    SCHEMA_PACKAGE,
)
from xcron_libs.domain import normalize_manifest

MANIFEST = """\
version: 1
project:
  id: surface-demo
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: alpha
    schedule:
      cron: "0 * * * *"
    command: echo alpha
"""


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    schedules = root / "schedules"
    schedules.mkdir(parents=True)
    (schedules / "default.yaml").write_text(textwrap.dedent(MANIFEST), encoding="utf-8")
    return root


def test_schema_ships_inside_the_module_that_owns_the_format() -> None:
    schema = load_schema()

    assert SCHEMA_PACKAGE == "xcron_libs.capabilities.manifest.resources.schemas"
    assert schema["type"] == "object"
    assert "jobs" in schema["properties"]


def test_loading_returns_the_document_the_contracts_describe(project: Path) -> None:
    document = load_project_manifest(project)

    assert document.project_root == project.resolve()
    assert document.manifest_path == (project / "schedules" / "default.yaml").resolve()
    assert document.raw_data["project"]["id"] == "surface-demo"
    assert document.manifest is None


def test_a_valid_manifest_produces_no_schema_errors(project: Path) -> None:
    document = load_project_manifest(project)

    errors, warnings = split_validation_messages(validate_schema(document.raw_data))

    assert errors == ()
    assert warnings == ()


def test_hashing_is_stable_across_two_independent_loads(project: Path) -> None:
    def hashes():
        document = load_project_manifest(project)
        manifest = parse_project_manifest(document.raw_data)
        normalized = normalize_manifest(manifest, document.project_root, document.manifest_path)
        return build_manifest_hashes(normalized)

    first, second = hashes(), hashes()

    assert first.manifest_hash == second.manifest_hash
    assert first.job_hashes == second.job_hashes


def test_adding_a_duplicate_job_raises_the_modules_typed_error(project: Path) -> None:
    with pytest.raises(ManifestJobAlreadyExistsError):
        add_manifest_job(
            {"id": "alpha", "schedule": {"cron": "0 * * * *"}, "command": "echo again"},
            project,
        )


def test_a_missing_schedules_directory_raises_manifest_not_found(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(ManifestNotFoundError):
        resolve_manifest_path(empty)


def test_two_manifests_without_a_selection_raise_ambiguous_selection(project: Path) -> None:
    (project / "schedules" / "other.yaml").write_text(
        textwrap.dedent(MANIFEST).replace("surface-demo", "other-demo"), encoding="utf-8"
    )

    with pytest.raises(AmbiguousManifestSelectionError):
        resolve_manifest_path(project)

    assert resolve_manifest_path(project, schedule_name="other").stem == "other"

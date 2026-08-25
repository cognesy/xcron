"""End-to-end contract checks for the self-contained YAML manifest provider."""

from __future__ import annotations

from xcron.capabilities.manifest_yaml.provider import CAPABILITY
from xcron.contracts import (
    InvocationContext,
    JobLookupRequest,
    JobCreateRequest,
    JobUpdateRequest,
    ManifestPort,
    ProjectRequest,
    ProjectWorkspace,
    Settings,
    XcronOptions,
)
from xcron.kernel import CapabilityHost, CapabilityRegistry


MANIFEST = """\
version: 1
project:
  id: demo
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: archive
    command: echo old
    schedule:
      cron: "0 * * * *"
"""


def test_provider_validates_normalizes_hashes_and_edits(tmp_path) -> None:
    """All manifest behaviours are reached via one kernel-selected port."""
    schedules = tmp_path / "schedules"
    schedules.mkdir()
    manifest_path = schedules / "default.yaml"
    manifest_path.write_text(MANIFEST, encoding="utf-8")
    workspace = ProjectWorkspace(
        root=tmp_path,
        manifest_dir=schedules,
        config_path=tmp_path / "config.yaml",
        marker_path=tmp_path / "marker.toml",
        marker=None,
    )
    context = InvocationContext(
        options=XcronOptions.create(tmp_path),
        workspace=workspace,
        settings=Settings(),
    )
    host = CapabilityHost(CapabilityRegistry((CAPABILITY,)))
    provider = host.require("manifest", ManifestPort)

    document = provider.load(ProjectRequest(), context)
    report = provider.validate(document, context)
    normalized = provider.normalize(document, context)
    hashes = provider.hashes(normalized)
    created = provider.create_job(
        JobCreateRequest(job_id="cleanup", command="echo cleanup", schedule={"kind": "every", "value": "1h"}),
        context,
    )
    mutation = provider.edit(
        JobLookupRequest(job_identifier="archive"),
        JobUpdateRequest(command="echo new"),
        context,
    )

    assert report.valid is True
    assert normalized.jobs[0].qualified_id == "demo.archive"
    assert hashes.job_hashes["demo.archive"]
    assert created.raw_job == {"id": "cleanup", "command": "echo cleanup", "schedule": {"every": "1h"}, "enabled": True}
    assert mutation.changed is True
    assert mutation.raw_jobs[0]["command"] == "echo new"
    assert "echo new" in manifest_path.read_text(encoding="utf-8")
    assert host.freeze().ids() == ("manifest:yaml",)

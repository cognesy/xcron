"""Contract and resource checks for the local workspace provider wheel."""

from __future__ import annotations

from importlib.resources import files

from xcron.capabilities.workspace_local.provider import CAPABILITY
from xcron.contracts import (
    NormalizedExecutionConfig,
    NormalizedJob,
    OverlapPolicy,
    ProjectRequest,
    ScheduleDefinition,
    ScheduleKind,
    WorkspacePort,
)
from xcron.kernel import CapabilityHost, CapabilityRegistry


def test_provider_initializes_and_resolves_a_workspace(tmp_path) -> None:
    """The kernel reaches all workspace behaviour through the public port."""
    host = CapabilityHost(CapabilityRegistry((CAPABILITY,)))
    workspace = host.require("workspace", WorkspacePort)

    result = workspace.initialize(tmp_path, created_by="provider-test")

    assert result.created is True
    assert (tmp_path / "schedules" / "default.yaml").read_text(encoding="utf-8") == files(
        "xcron.capabilities.workspace_local.resources"
    ).joinpath("starter-manifest.yaml").read_text(encoding="utf-8")
    resolved = workspace.resolve_workspace(ProjectRequest(project_path=tmp_path), environ={})
    assert resolved.root == tmp_path
    assert resolved.is_marked is True
    assert host.freeze().ids() == ("workspace:local",)


def test_provider_derives_runtime_paths_from_contract_job(tmp_path) -> None:
    """Runtime layout accepts the provider-neutral normalized-job value."""
    host = CapabilityHost(CapabilityRegistry((CAPABILITY,)))
    workspace = host.require("workspace", WorkspacePort)
    job = NormalizedJob(
        project_id="demo",
        job_id="archive",
        qualified_id="demo:archive",
        artifact_id="demo-archive",
        enabled=True,
        schedule=ScheduleDefinition(ScheduleKind.CRON, "0 * * * *"),
        execution=NormalizedExecutionConfig(
            command="echo archive",
            working_dir=".",
            shell="/bin/sh",
            timezone=None,
            env=(),
            overlap=OverlapPolicy.ALLOW,
        ),
    )

    paths = workspace.runtime_paths(job, state_root=tmp_path)

    assert paths.wrapper_path == tmp_path / "projects" / "demo" / "wrappers" / "demo-archive.sh"

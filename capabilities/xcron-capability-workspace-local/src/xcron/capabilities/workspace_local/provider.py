"""Installed entry point and public workspace-port adapter."""

from __future__ import annotations

from importlib.resources import files
import os
from pathlib import Path
from typing import Mapping

from xcron.capabilities.workspace_local import api
from xcron.contracts import ProjectRequest, WorkspacePort
from xcron.contracts.domain import NormalizedJob, ProjectWorkspace, RuntimePaths, WorkspaceInitResult, XcronHome
from xcron.kernel import (
    AssetDeclaration,
    Capability,
    CapabilityDescriptor,
    CapabilityProvides,
    CapabilityRegistration,
)


class LocalWorkspaceProvider:
    """The local-filesystem implementation of xcron's workspace port."""

    def resolve_workspace(
        self,
        request: ProjectRequest,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> ProjectWorkspace:
        return api.resolve_workspace(request.project_path, env=os.environ if environ is None else environ)

    def initialize(self, root: Path | None, *, created_by: str) -> WorkspaceInitResult:
        return api.initialize_workspace(root, created_by=created_by)

    def home(self, root: Path | None = None) -> XcronHome:
        return api.xcron_home_layout(root)

    def runtime_paths(self, job: NormalizedJob, *, state_root: Path | None = None) -> RuntimePaths:
        return api.resolve_runtime_paths(job, state_root=state_root)

    def project_state_path(self, project_id: str, *, state_root: Path | None = None) -> Path:
        return api.resolve_project_state_dir(project_id, state_root=state_root) / "project-state.json"


DESCRIPTOR = CapabilityDescriptor(
    capability="workspace",
    implementation="local",
    version="0.1.0",
    kernel_api=">=1,<2",
    provides=CapabilityProvides(ports=("workspace",), cli_paths=("init",), assets=("starter-manifest",)),
    assets=(AssetDeclaration("starter-manifest", "resources/starter-manifest.yaml"),),
)


def _build(_: object) -> CapabilityRegistration:
    return CapabilityRegistration(
        ports={"workspace": LocalWorkspaceProvider()},
        cli_paths={"init": None},
        assets={
            "starter-manifest": files("xcron.capabilities.workspace_local.resources").joinpath(
                "starter-manifest.yaml"
            )
        },
    )


CAPABILITY = Capability(DESCRIPTOR, _build)

assert isinstance(LocalWorkspaceProvider(), WorkspacePort)

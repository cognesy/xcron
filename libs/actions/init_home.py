"""Compatibility import for the workspace initialization capability."""

from xcron_libs.capabilities.workspace.api import initialize_workspace
from xcron_libs.capabilities.workspace.contracts import WorkspaceInitResult

#: Historic names. `init_home` initialized the xcron home only; the capability
#: now initializes any workspace, of which the home is one.
InitHomeResult = WorkspaceInitResult
init_home = initialize_workspace

__all__ = ["InitHomeResult", "init_home", "initialize_workspace", "WorkspaceInitResult"]

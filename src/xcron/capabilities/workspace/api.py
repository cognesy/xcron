"""Public callable surface of the workspace module.

Outside code imports this module and
:mod:`xcron.capabilities.workspace.contracts`, and nothing else below this
package.
"""

from __future__ import annotations

from xcron.capabilities.workspace.initializer import initialize_workspace
from xcron.capabilities.workspace.marker import (
    MARKER_FILENAME,
    MARKER_KIND,
    MARKER_SCHEMA,
    SUPPORTED_MARKER_SCHEMAS,
    marker_path,
    read_marker,
    render_marker,
    write_marker,
)
from xcron.capabilities.workspace.paths import (
    STATE_ENV_VAR,
    ensure_runtime_dirs,
    resolve_project_state_dir,
    resolve_runtime_paths,
    resolve_state_root,
    runtime_event_log_path_for_wrapper,
    runtime_log_paths_for_wrapper,
    xcron_home_layout,
)
from xcron.capabilities.workspace.resolver import (
    LEGACY_MANIFEST_DIR,
    MANIFEST_DIR,
    WORKSPACE_CONFIG_NAME,
    XCRON_HOME_ENV_VAR,
    XCRON_PROJECT_ENV_VAR,
    find_workspace_root,
    is_workspace,
    resolve_manifest_dir,
    resolve_project_root,
    resolve_workspace,
    resolve_xcron_home,
)

__all__ = [
    "LEGACY_MANIFEST_DIR",
    "MANIFEST_DIR",
    "MARKER_FILENAME",
    "MARKER_KIND",
    "MARKER_SCHEMA",
    "STATE_ENV_VAR",
    "SUPPORTED_MARKER_SCHEMAS",
    "WORKSPACE_CONFIG_NAME",
    "XCRON_HOME_ENV_VAR",
    "XCRON_PROJECT_ENV_VAR",
    "ensure_runtime_dirs",
    "find_workspace_root",
    "initialize_workspace",
    "is_workspace",
    "marker_path",
    "read_marker",
    "render_marker",
    "resolve_manifest_dir",
    "resolve_project_root",
    "resolve_project_state_dir",
    "resolve_runtime_paths",
    "resolve_state_root",
    "resolve_workspace",
    "resolve_xcron_home",
    "runtime_event_log_path_for_wrapper",
    "runtime_log_paths_for_wrapper",
    "write_marker",
    "xcron_home_layout",
]

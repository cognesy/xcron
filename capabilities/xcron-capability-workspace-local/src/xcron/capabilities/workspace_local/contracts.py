"""Compatibility names owned by the provider-neutral contracts package."""

from xcron.contracts.domain import ProjectWorkspace, RuntimePaths, WorkspaceInitResult, WorkspaceMarker, XcronHome
from xcron.contracts.results import (
    MalformedMarkerError,
    UnsupportedMarkerSchemaError,
    UnsupportedPlatformError,
    WorkspaceError,
    WorkspaceMarkerError,
    WorkspaceResolutionError,
)

__all__ = [
    "MalformedMarkerError",
    "ProjectWorkspace",
    "RuntimePaths",
    "UnsupportedMarkerSchemaError",
    "UnsupportedPlatformError",
    "WorkspaceError",
    "WorkspaceInitResult",
    "WorkspaceMarker",
    "WorkspaceMarkerError",
    "WorkspaceResolutionError",
    "XcronHome",
]

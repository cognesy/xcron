"""Context-independent service layer for xcron."""
"""Reusable services for xcron actions."""

from libs.services.config_loader import (
    MANIFEST_DIR,
    MANIFEST_SUFFIXES,
    AmbiguousManifestSelectionError,
    LoadedManifestDocument,
    ManifestLoadError,
    ManifestNotFoundError,
    ManifestParseError,
    ProjectResolutionError,
    attach_parsed_manifest,
    load_project_manifest,
    resolve_manifest_path,
    resolve_project_root,
)
from libs.services.hash_service import ManifestHashes, build_manifest_hashes
from libs.services.logging_paths import RuntimePaths, ensure_runtime_dirs, resolve_runtime_paths, runtime_log_paths_for_wrapper
from libs.services.observability import (
    check_output_logged,
    configure_logging,
    get_logger,
    instrument_action,
    run_logged_subprocess,
)
from libs.services.schema_validator import ValidationMessage, validate_schema, validate_semantics
from libs.services.state_store import (
    STATE_ENV_VAR,
    default_backend_for_current_platform,
    delete_project_state,
    load_project_state,
    resolve_project_state_dir,
    resolve_project_state_path,
    resolve_state_root,
    save_project_state,
)
from libs.services.wrapper_renderer import RenderedWrapper, render_wrapper, write_wrapper

__all__ = [
    "AmbiguousManifestSelectionError",
    "MANIFEST_DIR",
    "MANIFEST_SUFFIXES",
    "LoadedManifestDocument",
    "ManifestHashes",
    "ManifestLoadError",
    "ManifestNotFoundError",
    "ManifestParseError",
    "ProjectResolutionError",
    "RenderedWrapper",
    "RuntimePaths",
    "STATE_ENV_VAR",
    "ValidationMessage",
    "attach_parsed_manifest",
    "build_manifest_hashes",
    "check_output_logged",
    "configure_logging",
    "default_backend_for_current_platform",
    "delete_project_state",
    "ensure_runtime_dirs",
    "get_logger",
    "instrument_action",
    "load_project_manifest",
    "load_project_state",
    "render_wrapper",
    "resolve_manifest_path",
    "resolve_project_root",
    "resolve_project_state_dir",
    "resolve_project_state_path",
    "resolve_state_root",
    "resolve_runtime_paths",
    "runtime_log_paths_for_wrapper",
    "run_logged_subprocess",
    "save_project_state",
    "validate_schema",
    "validate_semantics",
    "write_wrapper",
]

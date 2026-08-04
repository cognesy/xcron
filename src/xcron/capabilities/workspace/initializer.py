"""Bringing a workspace into existence, idempotently and without destruction.

Init is the one operation that writes to a directory xcron does not yet own, so
it is deliberately timid: it creates what is missing, leaves what is present,
and reports anything that occupies a needed path but is not what xcron expects.
It never overwrites and never deletes. A conflict is information for an
operator, not a problem for xcron to solve on its own.

Running it twice is the same as running it once. Running it on a workspace
created before the marker existed adds the marker and changes nothing else.
"""

from __future__ import annotations

from pathlib import Path

from xcron.capabilities.workspace.contracts import (
    WorkspaceInitResult,
    WorkspaceMarkerError,
)
from xcron.capabilities.workspace.marker import (
    MARKER_KIND,
    marker_path,
    read_marker,
    write_marker,
)
from xcron.capabilities.workspace.paths import xcron_home_layout
from xcron.capabilities.workspace.resolver import LEGACY_MANIFEST_DIR
from xcron.shared.observability import get_logger, instrument_action

LOGGER = get_logger(__name__)

STARTER_MANIFEST = """\
version: 1
project:
  id: my-schedules
defaults:
  working_dir: "~"
  shell: /bin/sh
jobs: []
"""


@instrument_action("init_workspace")
def initialize_workspace(
    root: Path | None = None,
    *,
    created_by: str = "xcron",
) -> WorkspaceInitResult:
    """Create or complete one workspace, reporting exactly what changed."""
    layout = xcron_home_layout(root)
    created: list[str] = []
    retained: list[str] = []
    migrated: list[str] = []
    conflicts: list[str] = []

    legacy_schedules = layout.root / LEGACY_MANIFEST_DIR
    if not layout.schedules_dir.exists() and legacy_schedules.is_dir():
        # The legacy location is adopted where it stands. Moving a directory
        # xcron did not create is exactly the destructive step init refuses to
        # take; `resolve_manifest_dir` already reads both locations.
        migrated.append(str(legacy_schedules))
        LOGGER.info("legacy_schedules_adopted", schedules_dir=str(legacy_schedules))
    elif layout.schedules_dir.is_dir():
        retained.append(str(layout.schedules_dir))
    elif layout.schedules_dir.exists():
        conflicts.append(f"{layout.schedules_dir} exists and is not a directory")
    else:
        layout.schedules_dir.mkdir(parents=True)
        created.append(str(layout.schedules_dir))

    manifest_created = False
    if layout.manifest_path.exists():
        retained.append(str(layout.manifest_path))
        LOGGER.info("manifest_exists", manifest_path=str(layout.manifest_path))
    elif migrated or conflicts:
        # Nothing was written where the manifest would go, so do not claim a
        # location that the adopted or conflicting layout already answers for.
        LOGGER.info("manifest_skipped", manifest_path=str(layout.manifest_path))
    else:
        layout.manifest_path.write_text(STARTER_MANIFEST, encoding="utf-8")
        created.append(str(layout.manifest_path))
        manifest_created = True
        LOGGER.info("manifest_created", manifest_path=str(layout.manifest_path))

    _apply_marker(layout.root, created=created, retained=retained, conflicts=conflicts,
                  created_by=created_by)

    return WorkspaceInitResult(
        xcron_home=str(layout.root),
        schedules_dir=str(layout.schedules_dir),
        manifest_path=str(layout.manifest_path),
        marker_path=str(marker_path(layout.root)),
        created=manifest_created,
        created_paths=tuple(created),
        retained_paths=tuple(retained),
        migrated_paths=tuple(migrated),
        conflicts=tuple(conflicts),
    )


def _apply_marker(
    root: Path,
    *,
    created: list[str],
    retained: list[str],
    conflicts: list[str],
    created_by: str,
) -> None:
    """Add the marker if it is absent; never rewrite one that is already right."""
    path = marker_path(root)
    try:
        existing = read_marker(root)
    except WorkspaceMarkerError as exc:  # reported, never replaced
        conflicts.append(f"{path} is present but unusable: {exc}")
        return

    if existing is not None:
        retained.append(str(path))
        return

    if path.exists():
        conflicts.append(f"{path} exists and is not an {MARKER_KIND} marker")
        return

    write_marker(root, created_by=created_by)
    created.append(str(path))
    LOGGER.info("workspace_marker_created", marker=str(path))


__all__ = ["STARTER_MANIFEST", "initialize_workspace"]

"""The file that says "this directory is an xcron workspace, on purpose".

Without a marker, "is this a workspace?" is answered by guessing at layout: a
directory containing `schedules/` looks like one whether or not anyone meant it
to. That guess is fine until xcron writes something, at which point it is
guessing about someone else's directory.

The marker replaces the guess with a statement. It carries a schema number so
that a later layout change is a refusal rather than a misread, and the name of
the build that wrote it so an operator can tell where a workspace came from.

Adoption is staged. A missing marker is a warning for one release, because
every workspace in existence predates this file. A marker that is present but
wrong is an error from the start, because a wrong statement is worse than no
statement.
"""

from __future__ import annotations

from pathlib import Path
import tomllib

from xcron.capabilities.workspace_local.contracts import (
    MalformedMarkerError,
    UnsupportedMarkerSchemaError,
    WorkspaceMarker,
)

MARKER_FILENAME = "marker.toml"
MARKER_KIND = "xcron-workspace"

#: The layout this build writes and the only one it reads. Bump when the
#: on-disk layout of a workspace changes incompatibly.
MARKER_SCHEMA = 1

#: Schemas this build understands. Older builds refuse newer workspaces rather
#: than reading them with the wrong layout in mind.
SUPPORTED_MARKER_SCHEMAS = (1,)

MISSING_MARKER_HINT = "run `xcron init --project <dir>` to mark this directory as a workspace"


def marker_path(root: Path) -> Path:
    """The marker file for one workspace root."""
    return (Path(root) / MARKER_FILENAME).resolve()


def read_marker(root: Path) -> WorkspaceMarker | None:
    """Read and validate one workspace's marker, or ``None`` when absent.

    Absence is a caller decision, not a failure. Presence with the wrong
    contents always is.
    """
    path = marker_path(root)
    if not path.exists():
        return None
    if not path.is_file():
        raise MalformedMarkerError(f"workspace marker is not a file: {path}")

    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise MalformedMarkerError(f"cannot parse workspace marker {path}: {exc}") from exc
    except OSError as exc:
        raise MalformedMarkerError(f"cannot read workspace marker {path}: {exc}") from exc

    kind = payload.get("kind")
    if kind != MARKER_KIND:
        raise MalformedMarkerError(
            f"workspace marker {path} declares kind {kind!r}, expected {MARKER_KIND!r}"
        )

    schema = payload.get("schema")
    if not isinstance(schema, int) or isinstance(schema, bool):
        raise MalformedMarkerError(
            f"workspace marker {path} declares a non-integer schema: {schema!r}"
        )
    if schema not in SUPPORTED_MARKER_SCHEMAS:
        supported = ", ".join(str(value) for value in SUPPORTED_MARKER_SCHEMAS)
        raise UnsupportedMarkerSchemaError(
            f"workspace marker {path} declares schema {schema}, "
            f"this build supports {supported}; upgrade xcron to use this workspace"
        )

    created_by = payload.get("created_by", "")
    if not isinstance(created_by, str):
        raise MalformedMarkerError(
            f"workspace marker {path} declares a non-string created_by: {created_by!r}"
        )

    return WorkspaceMarker(kind=kind, schema=schema, created_by=created_by)


def write_marker(root: Path, *, created_by: str) -> WorkspaceMarker:
    """Write the marker for one workspace root, replacing any existing file."""
    marker = WorkspaceMarker(kind=MARKER_KIND, schema=MARKER_SCHEMA, created_by=created_by)
    marker_path(root).write_text(render_marker(marker), encoding="utf-8")
    return marker


def render_marker(marker: WorkspaceMarker) -> str:
    """Render a marker as TOML.

    Hand-rendered rather than serialized: the document is three scalars with a
    fixed shape, and the standard library has no TOML writer. Values are
    constrained by :class:`WorkspaceMarker`, so the only quoting needed is for
    `created_by`.
    """
    return (
        f'kind = "{marker.kind}"\n'
        f"schema = {marker.schema}\n"
        f'created_by = "{_escape(marker.created_by)}"\n'
    )


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


__all__ = [
    "MARKER_FILENAME",
    "MARKER_KIND",
    "MARKER_SCHEMA",
    "MISSING_MARKER_HINT",
    "SUPPORTED_MARKER_SCHEMAS",
    "marker_path",
    "read_marker",
    "render_marker",
    "write_marker",
]

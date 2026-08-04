"""The workspace marker, and what xcron does when it cannot trust one.

The marker's whole purpose is to turn a guess into a statement, so the cases
that matter are the ones where the statement is absent, unreadable, or from a
future xcron. Those three are deliberately handled differently, and this lane
pins which is which.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xcron_libs.capabilities.workspace.api import (
    MARKER_FILENAME,
    MARKER_KIND,
    MARKER_SCHEMA,
    marker_path,
    read_marker,
    render_marker,
    resolve_workspace,
    write_marker,
)
from xcron_libs.capabilities.workspace.contracts import (
    MalformedMarkerError,
    UnsupportedMarkerSchemaError,
    WorkspaceMarker,
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    (root / "schedules").mkdir(parents=True)
    return root


def test_a_written_marker_reads_back_as_what_was_written(workspace: Path) -> None:
    written = write_marker(workspace, created_by="xcron 9.9.9")

    assert written == WorkspaceMarker(
        kind=MARKER_KIND, schema=MARKER_SCHEMA, created_by="xcron 9.9.9"
    )
    assert read_marker(workspace) == written
    assert marker_path(workspace).name == MARKER_FILENAME


def test_the_rendered_document_is_the_durable_format(workspace: Path) -> None:
    """This exact text is on operators' disks. Changing it is a schema bump."""
    write_marker(workspace, created_by="xcron 0.1.0")

    assert marker_path(workspace).read_text(encoding="utf-8") == (
        'kind = "xcron-workspace"\n'
        "schema = 1\n"
        'created_by = "xcron 0.1.0"\n'
    )


def test_a_quote_in_created_by_survives_the_round_trip(workspace: Path) -> None:
    write_marker(workspace, created_by='xcron "edge" \\ build')

    assert read_marker(workspace).created_by == 'xcron "edge" \\ build'


def test_an_absent_marker_is_not_an_error(workspace: Path) -> None:
    assert read_marker(workspace) is None


def test_unparseable_contents_are_malformed(workspace: Path) -> None:
    marker_path(workspace).write_text("kind = = =", encoding="utf-8")

    with pytest.raises(MalformedMarkerError, match="cannot parse"):
        read_marker(workspace)


def test_another_tools_marker_is_malformed_rather_than_adopted(workspace: Path) -> None:
    marker_path(workspace).write_text('kind = "someone-else"\nschema = 1\n', encoding="utf-8")

    with pytest.raises(MalformedMarkerError, match="expected"):
        read_marker(workspace)


def test_a_non_integer_schema_is_malformed(workspace: Path) -> None:
    marker_path(workspace).write_text(
        'kind = "xcron-workspace"\nschema = "one"\n', encoding="utf-8"
    )

    with pytest.raises(MalformedMarkerError, match="non-integer schema"):
        read_marker(workspace)


def test_a_future_schema_is_refused_with_an_upgrade_hint(workspace: Path) -> None:
    marker_path(workspace).write_text(
        render_marker(WorkspaceMarker(kind=MARKER_KIND, schema=99, created_by="xcron 9.0")),
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedMarkerSchemaError, match="upgrade xcron"):
        read_marker(workspace)


def test_a_directory_where_the_marker_belongs_is_malformed(workspace: Path) -> None:
    marker_path(workspace).mkdir()

    with pytest.raises(MalformedMarkerError, match="not a file"):
        read_marker(workspace)


def test_an_unmarked_workspace_warns_and_proceeds(workspace: Path) -> None:
    """Decision 3: advisory for one release, so existing installs keep working."""
    warned: list[Path] = []

    resolved = resolve_workspace(workspace, on_missing_marker=warned.append)

    assert warned == [workspace.resolve()]
    assert resolved.root == workspace.resolve()
    assert resolved.marker is None
    assert resolved.is_marked is False


def test_a_marked_workspace_reports_its_marker_and_warns_nobody(workspace: Path) -> None:
    write_marker(workspace, created_by="xcron 0.1.0")
    warned: list[Path] = []

    resolved = resolve_workspace(workspace, on_missing_marker=warned.append)

    assert warned == []
    assert resolved.is_marked is True
    assert resolved.marker.created_by == "xcron 0.1.0"


def test_an_untrustworthy_marker_stops_resolution_outright(workspace: Path) -> None:
    marker_path(workspace).write_text("not toml at all = = =", encoding="utf-8")

    with pytest.raises(MalformedMarkerError):
        resolve_workspace(workspace)

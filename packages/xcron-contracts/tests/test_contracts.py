"""Contract values stay strict, immutable, and free of product providers."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Protocol

import pytest
from pydantic import ValidationError

from xcron.contracts import (
    InvocationContext,
    AgentHooksPort,
    JobCreateRequest,
    JobManagementPort,
    JobUpdateField,
    JobUpdateRequest,
    NullOutcomeSink,
    LogPort,
    ManifestPort,
    MetricsPort,
    ObservabilityPort,
    ProjectWorkspace,
    ScheduleRequest,
    ScheduleControlPort,
    Settings,
    SettingsPort,
    WorkspacePort,
    XcronOptions,
)
from xcron.testing import PortConformanceError, assert_port


class JobsProvider:
    def list(self, *args: object) -> object: return None
    def show(self, *args: object) -> object: return None
    def create(self, *args: object) -> object: return None
    def update(self, *args: object) -> object: return None
    def enable(self, *args: object) -> object: return None
    def disable(self, *args: object) -> object: return None
    def remove(self, *args: object) -> object: return None


class IncompleteJobsProvider:
    def list(self, *args: object) -> object: return None


ALL_PORTS = (
    WorkspacePort,
    SettingsPort,
    ObservabilityPort,
    ManifestPort,
    ScheduleControlPort,
    JobManagementPort,
    LogPort,
    MetricsPort,
    AgentHooksPort,
)


def _provider_for(port: type[Protocol]) -> object:
    """Build a structural fake from the protocol's public method declarations."""
    methods = {
        name: (lambda *args, **kwargs: None)
        for name, value in port.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    return type(f"{port.__name__}Fake", (), methods)()


def test_contract_values_are_immutable_and_requests_reject_unknown_fields(tmp_path: Path) -> None:
    options = XcronOptions.create(project_path=tmp_path, state_root=tmp_path / "state")
    workspace = ProjectWorkspace(
        root=tmp_path,
        manifest_dir=tmp_path / "resources/schedules",
        config_path=tmp_path / "config.yaml",
        marker_path=tmp_path / "marker.toml",
        marker=None,
    )
    context = InvocationContext(options=options, workspace=workspace, settings=Settings())

    assert isinstance(context.event_sink, NullOutcomeSink)
    with pytest.raises(FrozenInstanceError):
        options.backend = "cron"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        JobCreateRequest(job_id="daily", command="true", schedule=ScheduleRequest.every("1h"), extra=True)


def test_typed_job_requests_preserve_clear_and_update_guards() -> None:
    request = JobUpdateRequest(command="echo updated", clear_fields=frozenset({JobUpdateField.ENV}))
    assert request.manifest_updates() == {"command": "echo updated"}
    assert request.manifest_clear_fields() == ("env",)

    with pytest.raises(ValidationError, match="cannot update and clear"):
        JobUpdateRequest(env={"A": "1"}, clear_fields=frozenset({JobUpdateField.ENV}))


def test_all_ports_are_runtime_checkable_with_positive_and_negative_conformance() -> None:
    for port in ALL_PORTS:
        assert_port(_provider_for(port), port)
        with pytest.raises(PortConformanceError, match=port.__name__):
            assert_port(object(), port)

    assert_port(JobsProvider(), JobManagementPort)
    with pytest.raises(PortConformanceError, match="JobManagementPort"):
        assert_port(IncompleteJobsProvider(), JobManagementPort)

    class NotRuntimeCheckable(Protocol):
        def value(self) -> str: ...

    with pytest.raises(TypeError, match="runtime_checkable"):
        assert_port(object(), NotRuntimeCheckable)


def test_contract_package_imports_no_provider_or_channel() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "xcron" / "contracts"
    for source in source_root.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        imports = {
            name
            for node in ast.walk(tree)
            for name in (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            )
        }
        assert not any(name == "xcron.capabilities" or name.startswith("xcron.capabilities.") for name in imports)
        assert not any(name == "xcron_cli" or name.startswith("xcron_cli.") for name in imports)

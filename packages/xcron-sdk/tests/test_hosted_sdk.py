"""Hosted SDK behavior independent of concrete provider implementation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from xcron.contracts import (
    ProjectRequest,
    ProjectWorkspace,
    RuntimePaths,
    Settings,
    WorkspaceInitResult,
    WorkspaceMarker,
    XcronHome,
)
from xcron.kernel import (
    Capability,
    CapabilityDescriptor,
    CapabilityHost,
    CapabilityProvides,
    CapabilityRegistration,
    CapabilityRegistry,
)
from xcron.kernel.errors import CapabilityUnavailableError
from xcron.sdk import ClientClosedError, Xcron


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SDK_SOURCE = PACKAGE_ROOT / "src" / "xcron" / "sdk"


class CountingWorkspace:
    """A complete test port that makes scoped composition observable."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.resolved = 0

    def resolve_workspace(self, request: ProjectRequest, *, environ: dict[str, str]) -> ProjectWorkspace:
        del request, environ
        self.resolved += 1
        return ProjectWorkspace(
            root=self.root,
            manifest_dir=self.root / "resources" / "schedules",
            config_path=self.root / "config.yaml",
            marker_path=self.root / "marker.toml",
            marker=WorkspaceMarker(kind="xcron", schema=1, created_by="test"),
        )

    def initialize(self, root: Path | None, *, created_by: str) -> WorkspaceInitResult:
        target = self.root if root is None else root
        return WorkspaceInitResult(
            xcron_home=str(target),
            schedules_dir=str(target / "schedules"),
            manifest_path=str(target / "schedules" / "default.yaml"),
            marker_path=str(target / "marker.toml"),
            created=False,
            created_paths=(),
            retained_paths=(),
            migrated_paths=(),
            conflicts=(),
        )

    def home(self, root: Path | None = None) -> XcronHome:
        target = self.root if root is None else root
        return XcronHome(target, target / "schedules", target / "schedules" / "default.yaml", target / "metrics.json", target / "marker.toml")

    def runtime_paths(self, job, *, state_root: Path | None = None) -> RuntimePaths:
        raise AssertionError("lean SDK test does not reconcile jobs")

    def project_state_path(self, project_id: str, *, state_root: Path | None = None) -> Path:
        raise AssertionError("lean SDK test does not inspect state")


class CountingSettings:
    """A complete settings port that records its one construction call."""

    def __init__(self) -> None:
        self.composed = 0

    def compose(self, workspace, options, *, environ) -> Settings:
        del workspace, options, environ
        self.composed += 1
        return Settings()


def _capability(name: str, implementation: object, port_name: str) -> Capability:
    return Capability(
        CapabilityDescriptor(
            capability=name,
            implementation="test",
            version="0.1.0",
            kernel_api=">=1,<2",
            provides=CapabilityProvides(ports=(port_name,)),
        ),
        lambda _host: CapabilityRegistration(ports={port_name: implementation}),
    )


def test_scoped_client_composes_workspace_and_settings_once_then_keeps_groups_lazy(tmp_path: Path) -> None:
    workspace = CountingWorkspace(tmp_path)
    settings = CountingSettings()
    registry = CapabilityRegistry(
        (
            _capability("workspace", workspace, "workspace"),
            _capability("settings", settings, "settings"),
        )
    )

    with Xcron.open(tmp_path, capability_registry=registry, environ={}) as client:
        assert workspace.resolved == 1
        assert settings.composed == 1
        assert client.options.project_path == tmp_path.resolve()
        assert client.home.initialize().xcron_home == str(tmp_path)
        with pytest.raises(CapabilityUnavailableError, match="scheduler"):
            client.schedules

    with pytest.raises(ClientClosedError, match="xcron client is closed"):
        client.home


def test_unscoped_lean_client_exposes_an_empty_snapshot_and_defers_unavailable_groups() -> None:
    client = Xcron.open_unscoped(capability_registry=CapabilityRegistry(()))

    assert client.capabilities.ids() == ()
    with pytest.raises(CapabilityUnavailableError, match="workspace"):
        client.home

    client.close()
    client.close()


def test_sdk_package_imports_only_kernel_contracts_and_own_modules() -> None:
    forbidden = ("xcron.capabilities", "xcron_cli", "typer", "rich", "toon")

    for path in SDK_SOURCE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imports(tree)
        assert not any(name.startswith(forbidden) for name in imported), path


def test_sdk_import_boundary_rejects_a_direct_provider_import() -> None:
    """Keep the negative control next to the SDK source boundary it protects."""
    imported = _imports(ast.parse("from xcron.capabilities.scheduler_native import provider"))

    assert any(name.startswith("xcron.capabilities") for name in imported)


def test_host_is_immutable_after_open(tmp_path: Path) -> None:
    workspace = CountingWorkspace(tmp_path)
    settings = CountingSettings()
    host = CapabilityHost(
        CapabilityRegistry(
            (
                _capability("workspace", workspace, "workspace"),
                _capability("settings", settings, "settings"),
            )
        )
    )

    # Passing a registry always creates the one snapshot once; callers cannot
    # mutate selection through a public SDK group later.
    with Xcron.open(tmp_path, capability_registry=host.registry, environ={}) as client:
        assert client.capabilities.ids() == ("settings:test", "workspace:test")


def _imports(tree: ast.AST) -> set[str]:
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imported

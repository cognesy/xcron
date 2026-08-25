"""The generic testing wheel proves port and package-boundary failures clearly."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest

from xcron.testing import PortConformanceError, assert_port, check_package_boundaries, source_roots


@runtime_checkable
class GreetingPort(Protocol):
    def greet(self) -> str: ...


class Greeter:
    def greet(self) -> str:
        return "hello"


def test_structural_port_conformance_accepts_and_rejects_values() -> None:
    assert_port(Greeter(), GreetingPort)
    with pytest.raises(PortConformanceError, match="GreetingPort"):
        assert_port(object(), GreetingPort)


def test_workspace_scan_finds_kernel_and_provider_boundary_leaks(tmp_path: Path) -> None:
    kernel = tmp_path / "packages/xcron-kernel/src/xcron/kernel/kernel.py"
    provider = tmp_path / "capabilities/xcron-capability-demo/src/xcron/capabilities/demo/core.py"
    peer = tmp_path / "capabilities/xcron-capability-peer/src/xcron/capabilities/peer/api.py"
    for path, content in (
        (kernel, "import xcron.capabilities.manifest\n"),
        (provider, "import xcron.capabilities.peer._private\nimport xcron_cli\n"),
        (peer, "from xcron.contracts import ProjectRequest\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    violations = check_package_boundaries(tmp_path)
    assert {(item.rule, item.detail) for item in violations} == {
        ("kernel-product", "xcron.capabilities.manifest"),
        ("provider-peer-import", "xcron.capabilities.peer._private"),
        ("provider-channel", "xcron_cli"),
    }
    assert source_roots(tmp_path) == tuple(sorted(source_roots(tmp_path), key=str))


def test_workspace_scan_rejects_even_declared_peer_surfaces(tmp_path: Path) -> None:
    provider = tmp_path / "capabilities/xcron-capability-demo/src/xcron/capabilities/demo/core.py"
    provider.parent.mkdir(parents=True)
    provider.write_text(
        "from xcron.capabilities.peer.api import PeerPort\nfrom xcron.capabilities.peer.contracts import PeerResult\n",
        encoding="utf-8",
    )

    assert {(item.rule, item.detail) for item in check_package_boundaries(tmp_path)} == {
        ("provider-peer-import", "xcron.capabilities.peer.api"),
        ("provider-peer-import", "xcron.capabilities.peer.contracts"),
    }

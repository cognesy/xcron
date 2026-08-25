from __future__ import annotations

import ast
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace
import tomllib

import pytest

from xcron.contracts import CliContribution
from xcron.kernel import Capability, CapabilityDescriptor, CapabilityProvides, CapabilityRegistry
from xcron_cli.contributions import CliContributionError, attach_cli_contributions, contributions_for, validate_contributions


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class FakeApplication:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.groups: list[tuple[object, str]] = []

    def command(self, name: str):
        def attach(function):
            self.commands.append(name)
            return function

        return attach

    def add_typer(self, group: object, *, name: str) -> None:
        self.groups.append((group, name))


def _registry() -> CapabilityRegistry:
    descriptor = CapabilityDescriptor(
        capability="workspace",
        implementation="local",
        version="0.1.0",
        kernel_api=">=1,<2",
        provides=CapabilityProvides(cli_paths=("init",)),
    )
    return CapabilityRegistry((Capability(descriptor, lambda host: None),))


def _symbols() -> dict[str, object]:
    return {"init_command": lambda: None}


def test_attaches_the_selected_descriptor_owned_command() -> None:
    application = FakeApplication()

    contributions = attach_cli_contributions(application, _symbols(), registry=_registry())

    assert [item.command_path for item in contributions] == [("init",)]
    assert application.commands == ["init"]
    assert application.groups == []


def test_rejects_a_declared_path_without_a_terminal_binding() -> None:
    descriptor = CapabilityDescriptor(
        capability="workspace",
        implementation="local",
        version="0.1.0",
        kernel_api=">=1,<2",
        provides=CapabilityProvides(cli_paths=("migrate",)),
    )

    with pytest.raises(CliContributionError, match="has no adapter") as raised:
        contributions_for(CapabilityRegistry((Capability(descriptor, lambda host: None),)).snapshot(), _symbols())

    assert raised.value.code == "cli_contribution_invalid"
    assert "binding" in raised.value.remedy


def test_rejects_two_contributions_for_one_path() -> None:
    snapshot = _registry().snapshot()
    first = CliContribution(("init",), "workspace", "local", "init", lambda: SimpleNamespace(register=lambda app: None))
    second = CliContribution(("init",), "workspace", "local", "init", lambda: SimpleNamespace(register=lambda app: None))

    with pytest.raises(CliContributionError, match="both workspace:local"):
        validate_contributions((first, second), snapshot)


def test_terminal_package_owns_its_console_script_and_authored_help() -> None:
    metadata = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"] == {"xcron": "xcron_cli.main:run"}
    assert "Authoritative runtime help" in files("xcron_cli.resources.help").joinpath("root.md").read_text()


def test_terminal_modules_do_not_import_a_provider_implementation() -> None:
    for source in (PACKAGE_ROOT / "src" / "xcron_cli").rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert not any(name.startswith("xcron.capabilities") for name in imported), source

"""Validate and attach terminal contributions declared by selected providers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from xcron.contracts import CliAdapter, CliContribution
from xcron.kernel import CapabilityDescriptor, CapabilityRegistry, CapabilitySelection, CapabilitySnapshot


class CliContributionError(ValueError):
    """Structured startup failure for an invalid CLI capability contribution."""

    code = "cli_contribution_invalid"

    def __init__(self, message: str, *, remedy: str) -> None:
        super().__init__(message)
        self.remedy = remedy


BindingKind = Literal["command", "group"]


@dataclass(frozen=True, slots=True)
class _Binding:
    """A bridge symbol that can become one descriptor-owned CLI path."""

    kind: BindingKind
    symbol: str


_BINDINGS: Mapping[str, Mapping[str, _Binding]] = {
    "workspace": {"init": _Binding("command", "init_command")},
    "scheduler": {
        "validate": _Binding("command", "validate_command"),
        "plan": _Binding("command", "plan_command"),
        "status": _Binding("command", "status_command"),
        "inspect": _Binding("command", "inspect_command"),
        "apply": _Binding("command", "apply_command"),
        "prune": _Binding("command", "prune_command"),
    },
    "jobs": {"jobs": _Binding("group", "jobs_app")},
    "logs": {"logs": _Binding("group", "logs_app")},
    "metrics": {"metrics": _Binding("group", "metrics_app")},
    "agent-hooks": {"hooks": _Binding("group", "hooks_app")},
}


@dataclass(frozen=True, slots=True)
class _CommandAdapter:
    """Attach a one-word command without importing any terminal library here."""

    name: str
    command: Callable[..., object]

    def register(self, application: object) -> None:
        decorator = getattr(application, "command", None)
        if not callable(decorator):
            raise CliContributionError(
                "CLI application does not support command registration.",
                remedy="Pass the channel application created by the CLI package.",
            )
        decorator(self.name)(self.command)


@dataclass(frozen=True, slots=True)
class _GroupAdapter:
    """Attach a command group without making provider code know Typer."""

    name: str
    group: object

    def register(self, application: object) -> None:
        add_typer = getattr(application, "add_typer", None)
        if not callable(add_typer):
            raise CliContributionError(
                "CLI application does not support command-group registration.",
                remedy="Pass the channel application created by the CLI package.",
            )
        add_typer(self.group, name=self.name)


def _path_text(path: tuple[str, ...]) -> str:
    return " ".join(path)


def _binding_for(descriptor: CapabilityDescriptor, path: str, symbols: Mapping[str, object]) -> CliContribution:
    binding = _BINDINGS.get(descriptor.capability, {}).get(path)
    if binding is None:
        raise CliContributionError(
            f"Selected provider {descriptor.id!r} declares CLI path {path!r}, but the CLI channel has no adapter.",
            remedy="Add a channel-owned binding for the declared path or remove the provider claim.",
        )
    value = symbols.get(binding.symbol)
    if value is None:
        raise CliContributionError(
            f"CLI adapter for {descriptor.id!r} path {path!r} is missing bridge symbol {binding.symbol!r}.",
            remedy="Expose the named command or command group from the terminal bridge.",
        )
    if binding.kind == "command":
        if not callable(value):
            raise CliContributionError(
                f"CLI adapter symbol {binding.symbol!r} for {descriptor.id!r} is not callable.",
                remedy="Bind a command function to that symbol.",
            )
        factory: Callable[[], CliAdapter] = lambda: _CommandAdapter(path, value)
    else:
        factory = lambda: _GroupAdapter(path, value)
    return CliContribution(
        command_path=(path,),
        capability=descriptor.capability,
        implementation=descriptor.implementation,
        help_key=path.replace(" ", "/"),
        factory=factory,
    )


def contributions_for(snapshot: CapabilitySnapshot, symbols: Mapping[str, object]) -> tuple[CliContribution, ...]:
    """Build one channel contribution for every selected descriptor CLI claim."""
    contributions: list[CliContribution] = []
    for descriptor in snapshot.descriptors:
        for path in descriptor.provides.cli_paths:
            contributions.append(_binding_for(descriptor, path, symbols))
    return tuple(contributions)


def validate_contributions(
    contributions: tuple[CliContribution, ...],
    snapshot: CapabilitySnapshot,
) -> None:
    """Reject unselected, undeclared, or overlapping channel command paths."""
    selected = {(descriptor.capability, descriptor.implementation): descriptor for descriptor in snapshot.descriptors}
    owners: dict[tuple[str, ...], CliContribution] = {}
    for contribution in contributions:
        descriptor = selected.get((contribution.capability, contribution.implementation))
        if descriptor is None:
            raise CliContributionError(
                f"CLI path {_path_text(contribution.command_path)!r} belongs to unselected provider "
                f"{contribution.capability}:{contribution.implementation}.",
                remedy="Construct CLI contributions only from the selected capability snapshot.",
            )
        declared = set(descriptor.provides.cli_paths)
        path = _path_text(contribution.command_path)
        if path not in declared:
            raise CliContributionError(
                f"CLI contribution {path!r} is not declared by selected provider {descriptor.id!r}.",
                remedy="Add the exact path to CapabilityProvides.cli_paths before registering it.",
            )
        owner = owners.setdefault(contribution.command_path, contribution)
        if owner is not contribution:
            raise CliContributionError(
                f"CLI path {path!r} is contributed by both "
                f"{owner.capability}:{owner.implementation} and "
                f"{contribution.capability}:{contribution.implementation}.",
                remedy="Select one provider or give the contributions distinct command paths.",
            )

    declared_paths = {
        (path,)
        for descriptor in snapshot.descriptors
        for path in descriptor.provides.cli_paths
    }
    contributed_paths = set(owners)
    missing = sorted(_path_text(path) for path in declared_paths - contributed_paths)
    if missing:
        raise CliContributionError(
            f"Selected CLI paths have no contribution: {', '.join(missing)}.",
            remedy="Provide a channel adapter for every selected descriptor CLI path.",
        )


def attach_cli_contributions(
    application: object,
    symbols: Mapping[str, object],
    *,
    registry: CapabilityRegistry | None = None,
    selection: CapabilitySelection | None = None,
) -> tuple[CliContribution, ...]:
    """Discover, validate, and attach the selected terminal contributions once."""
    active_registry = registry or CapabilityRegistry.from_entry_points()
    snapshot = active_registry.snapshot(selection)
    contributions = contributions_for(snapshot, symbols)
    validate_contributions(contributions, snapshot)
    for contribution in contributions:
        contribution.factory().register(application)
    return contributions

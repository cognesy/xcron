"""Construct the deterministic xcron runtime without channel dependencies.

This is the one place an invocation's scope is decided. The workspace is
resolved once, settings are composed once over it, and everything below
receives typed values. A capability that re-derives a path or reads an
environment variable is re-deciding something already decided here, and the two
answers are free to differ — which is the bug class this module exists to make
impossible.

Precedence is explicit and one-directional: an argument passed in beats a
setting, and a setting beats a default. Arguments come from a flag or an
embedder, so a caller who states a value always gets it.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping, TypeVar

from xcron.capabilities.operations.api import record_outcome
from xcron.capabilities.reconciliation.api import (
    SchedulerRegistry,
    default_scheduler_registry,
)
from xcron.capabilities.reconciliation.contracts import OutcomeRecorder
from xcron.capabilities.workspace.api import resolve_state_root, resolve_workspace
from xcron.capabilities.workspace.contracts import ProjectWorkspace
from xcron.configuration.api import load_settings
from xcron.configuration.contracts import Settings
from xcron.runtime.options import XcronOptions

T = TypeVar("T")


class MetricsOutcomeRecorder:
    """Adapt reconciliation's `OutcomeRecorder` port onto the operations module.

    This class is the only place the two capabilities meet. Reconciliation has
    no edge to operations; the composition root owns the wiring, so either side
    can be replaced without the other knowing.
    """

    def record(self, counter: str, amount: int = 1) -> None:
        record_outcome(counter, amount)


@dataclass(frozen=True)
class XcronRuntime:
    """Resolved invocation scope and provider set shared by every channel."""

    options: XcronOptions
    workspace: ProjectWorkspace | None
    settings: Settings
    scheduler_registry: SchedulerRegistry
    outcome_recorder: OutcomeRecorder

    @classmethod
    def create_unscoped(cls, **kwargs) -> XcronRuntime:
        """Compose a runtime for an operation that is not about a workspace.

        `init` runs before a workspace exists and `metrics` reads counters that
        live in the xcron home, not in any project. Forcing those to resolve a
        workspace would make `xcron init` fail on exactly the machine that needs
        it most. Such a runtime carries ``workspace=None`` rather than a
        plausible-looking default no one chose.
        """
        return cls._compose(workspace=None, **kwargs)

    @classmethod
    def create(
        cls,
        project_path: str | Path | None = None,
        *,
        schedule_name: str | None = None,
        backend: str | None = None,
        state_root: str | Path | None = None,
        platform: str | None = None,
        launch_agents_dir: str | Path | None = None,
        launchctl_domain: str | None = None,
        crontab_path: str | Path | None = None,
        manage_launchctl: bool | None = None,
        manage_crontab: bool | None = None,
        scheduler_registry: SchedulerRegistry | None = None,
        outcome_recorder: OutcomeRecorder | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> XcronRuntime:
        """Resolve scope and settings once, then use injected providers."""
        return cls._compose(
            workspace=resolve_workspace(
                project_path, env=dict(os.environ if environ is None else environ)
            ),
            schedule_name=schedule_name,
            backend=backend,
            state_root=state_root,
            platform=platform,
            launch_agents_dir=launch_agents_dir,
            launchctl_domain=launchctl_domain,
            crontab_path=crontab_path,
            manage_launchctl=manage_launchctl,
            manage_crontab=manage_crontab,
            scheduler_registry=scheduler_registry,
            outcome_recorder=outcome_recorder,
            environ=environ,
        )

    @classmethod
    def _compose(
        cls,
        *,
        workspace: ProjectWorkspace | None,
        schedule_name: str | None = None,
        backend: str | None = None,
        state_root: str | Path | None = None,
        platform: str | None = None,
        launch_agents_dir: str | Path | None = None,
        launchctl_domain: str | None = None,
        crontab_path: str | Path | None = None,
        manage_launchctl: bool | None = None,
        manage_crontab: bool | None = None,
        scheduler_registry: SchedulerRegistry | None = None,
        outcome_recorder: OutcomeRecorder | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> XcronRuntime:
        env = dict(os.environ if environ is None else environ)
        settings = load_settings(
            workspace_config_path=None if workspace is None else workspace.config_path,
            environ=env,
        )

        return cls(
            options=XcronOptions.create(
                None if workspace is None else workspace.root,
                schedule_name=schedule_name,
                backend=backend,
                state_root=resolve_state_root(
                    platform=platform,
                    override=_stated(state_root, settings.state_root),
                ),
                platform=platform,
                launch_agents_dir=_stated(launch_agents_dir, settings.launch_agents_dir),
                launchctl_domain=_stated(launchctl_domain, settings.launchctl_domain),
                crontab_path=_stated(crontab_path, settings.crontab_path),
                manage_launchctl=_stated(manage_launchctl, settings.manage_launchctl),
                manage_crontab=_stated(manage_crontab, settings.manage_crontab),
            ),
            workspace=workspace,
            settings=settings,
            scheduler_registry=scheduler_registry or default_scheduler_registry(),
            outcome_recorder=outcome_recorder or MetricsOutcomeRecorder(),
        )


def _stated(argument: T | None, setting: T) -> T:
    """The caller's value if they stated one, otherwise the composed setting."""
    return setting if argument is None else argument

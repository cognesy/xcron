"""Construct the deterministic xcron runtime without channel dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from xcron_libs.capabilities.operations.api import record_outcome
from xcron_libs.capabilities.reconciliation.api import (
    SchedulerRegistry,
    default_scheduler_registry,
)
from xcron_libs.capabilities.reconciliation.contracts import OutcomeRecorder
from xcron_libs.runtime.options import XcronOptions


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
    scheduler_registry: SchedulerRegistry
    outcome_recorder: OutcomeRecorder

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
        manage_launchctl: bool = True,
        manage_crontab: bool = True,
        scheduler_registry: SchedulerRegistry | None = None,
        outcome_recorder: OutcomeRecorder | None = None,
    ) -> XcronRuntime:
        """Resolve scope once and use injected or deterministic providers."""
        return cls(
            options=XcronOptions.create(
                project_path,
                schedule_name=schedule_name,
                backend=backend,
                state_root=state_root,
                platform=platform,
                launch_agents_dir=launch_agents_dir,
                launchctl_domain=launchctl_domain,
                crontab_path=crontab_path,
                manage_launchctl=manage_launchctl,
                manage_crontab=manage_crontab,
            ),
            scheduler_registry=scheduler_registry or default_scheduler_registry(),
            outcome_recorder=outcome_recorder or MetricsOutcomeRecorder(),
        )

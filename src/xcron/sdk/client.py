"""The public :class:`Xcron` client and composition root for embedders."""

from __future__ import annotations

from pathlib import Path

from xcron.capabilities.reconciliation.api import SchedulerRegistry
from xcron.runtime import XcronRuntime
from xcron.sdk.errors import ClientClosedError
from xcron.sdk.home import HomeAPI
from xcron.sdk.hooks import HooksAPI
from xcron.sdk.jobs import JobsAPI
from xcron.sdk.operations import OperationsAPI
from xcron.sdk.options import XcronOptions
from xcron.sdk.schedules import SchedulesAPI


class Xcron:
    """Synchronous typed client over xcron's capability/action layer.

    The client captures invocation scope and scheduler selection once. It owns
    no long-lived native-scheduler connection, but retains lifecycle semantics
    so later owned resources can be added without changing the public API.
    """

    def __init__(self, *, runtime: XcronRuntime) -> None:
        self._options = runtime.options
        self._runtime = runtime
        self._closed = False

    @classmethod
    def open(
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
    ) -> Xcron:
        """Open a client with explicit scope, host overrides, and providers.

        Every override defaults to ``None`` meaning "unstated", so the composed
        settings decide. Stating a value here always wins over configuration.
        """
        return cls(
            runtime=XcronRuntime.create(
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
                scheduler_registry=scheduler_registry,
            ),
        )

    @classmethod
    def open_unscoped(cls, *, scheduler_registry: SchedulerRegistry | None = None) -> Xcron:
        """Open a client for operations that are not about a workspace.

        Workspace initialization and the metrics counters both live in the
        xcron home. Resolving a workspace for them would make `init` fail on a
        machine that does not have one yet, which is the only machine that
        needs it.
        """
        return cls(runtime=XcronRuntime.create_unscoped(scheduler_registry=scheduler_registry))

    def close(self) -> None:
        """Close idempotently; the current runtime owns no persistent resource."""
        self._closed = True

    def __enter__(self) -> Xcron:
        self._guard()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def schedules(self) -> SchedulesAPI:
        self._guard()
        return SchedulesAPI(
            self._options,
            self._runtime.scheduler_registry,
            self._runtime.outcome_recorder,
            self._guard,
        )

    @property
    def jobs(self) -> JobsAPI:
        self._guard()
        return JobsAPI(self._options, self._guard)

    @property
    def operations(self) -> OperationsAPI:
        self._guard()
        return OperationsAPI(self._options, self._guard)

    @property
    def hooks(self) -> HooksAPI:
        self._guard()
        return HooksAPI(self._options, self._guard)

    @property
    def home(self) -> HomeAPI:
        self._guard()
        return HomeAPI(self._guard)

    @property
    def options(self) -> XcronOptions:
        """Return the resolved, immutable invocation scope."""
        self._guard()
        return self._options

    def _guard(self) -> None:
        if self._closed:
            raise ClientClosedError("xcron client is closed")

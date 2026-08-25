"""The public :class:`Xcron` client composed through a capability host."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from xcron.contracts import (
    AgentHooksPort,
    InvocationContext,
    JobManagementPort,
    LogPort,
    MetricsPort,
    NullOutcomeSink,
    ObservabilityPort,
    OutcomeSink,
    ProjectRequest,
    ScheduleControlPort,
    Settings,
    SettingsPort,
    WorkspacePort,
    XcronOptions,
)
from xcron.kernel import CapabilityHost, CapabilityRegistry, CapabilitySelection, CapabilitySnapshot
from xcron.kernel.errors import CapabilityUnavailableError
from xcron.sdk.errors import ClientClosedError
from xcron.sdk.home import HomeAPI
from xcron.sdk.hooks import HooksAPI
from xcron.sdk.jobs import JobsAPI
from xcron.sdk.operations import OperationsAPI
from xcron.sdk.schedules import SchedulesAPI


class Xcron:
    """Synchronous, typed client over the selected capability-host ports."""

    def __init__(self, *, host: CapabilityHost, context: InvocationContext) -> None:
        self._host = host
        self._context = context
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
        capability_registry: CapabilityRegistry | None = None,
        selection: CapabilitySelection | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> Xcron:
        """Open a scoped client from installed providers and explicit options."""
        host = _host(capability_registry, selection)
        _bootstrap_observability(host)
        request = ProjectRequest(project_path=_path(project_path), schedule_name=schedule_name)
        workspace = host.require("workspace", WorkspacePort).resolve_workspace(request, environ=environ)
        provisional = XcronOptions.create(
            workspace.root,
            schedule_name=schedule_name,
            backend=backend,
            state_root=state_root,
            platform=platform,
            launch_agents_dir=launch_agents_dir,
            launchctl_domain=launchctl_domain,
            crontab_path=crontab_path,
        )
        settings = host.require("settings", SettingsPort).compose(workspace, provisional, environ=environ)
        options = XcronOptions.create(
            workspace.root,
            schedule_name=schedule_name,
            backend=backend,
            state_root=_stated(state_root, settings.state_root),
            platform=platform,
            launch_agents_dir=_stated(launch_agents_dir, settings.launch_agents_dir),
            launchctl_domain=_stated(launchctl_domain, settings.launchctl_domain),
            crontab_path=_stated(crontab_path, settings.crontab_path),
            manage_launchctl=_stated(manage_launchctl, settings.manage_launchctl),
            manage_crontab=_stated(manage_crontab, settings.manage_crontab),
        )
        return cls(host=host, context=InvocationContext(options, workspace, settings))

    @classmethod
    def open_unscoped(
        cls,
        *,
        capability_registry: CapabilityRegistry | None = None,
        selection: CapabilitySelection | None = None,
    ) -> Xcron:
        """Open a host without requiring a workspace or settings capability."""
        return cls(
            host=_host(capability_registry, selection),
            context=InvocationContext(XcronOptions(), None, Settings()),
        )

    def close(self) -> None:
        """Close the underlying capability host idempotently."""
        if not self._closed:
            self._host.close()
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
            self._observed_port("scheduler", ScheduleControlPort),
            self._context_with_metrics(),
            self._guard,
        )

    @property
    def jobs(self) -> JobsAPI:
        self._guard()
        return JobsAPI(self._observed_port("jobs", JobManagementPort), self._context_with_metrics(), self._guard)

    @property
    def operations(self) -> OperationsAPI:
        self._guard()
        return OperationsAPI(
            self._observed_port("logs", LogPort),
            self._observed_port("metrics", MetricsPort),
            self._context_with_metrics(),
            self._guard,
        )

    @property
    def hooks(self) -> HooksAPI:
        self._guard()
        return HooksAPI(self._observed_port("agent-hooks", AgentHooksPort), self._context, self._guard)

    @property
    def home(self) -> HomeAPI:
        self._guard()
        return HomeAPI(self._observed_port("workspace", WorkspacePort), self._guard)

    @property
    def options(self) -> XcronOptions:
        """Return the resolved, immutable invocation scope."""
        self._guard()
        return self._context.options

    @property
    def capabilities(self) -> CapabilitySnapshot:
        """Return the immutable selected provider snapshot for this client."""
        self._guard()
        return self._host.snapshot

    def _context_with_metrics(self) -> InvocationContext:
        try:
            sink = self._host.require("metrics", MetricsPort).outcome_sink(self._context)
        except CapabilityUnavailableError:
            sink = NullOutcomeSink()
        except Exception:
            sink = NullOutcomeSink()
        return replace(self._context, event_sink=sink)

    def _observed_port(self, capability: str, port: type) -> object:
        """Decorate one public port with optional structured action events."""
        target = self._host.require(capability, port)
        try:
            sink = self._host.require("observability", ObservabilityPort).outcome_sink(self._context)
        except CapabilityUnavailableError:
            sink = NullOutcomeSink()
        except Exception:
            sink = NullOutcomeSink()
        return _ObservedPort(target, sink)

    def _guard(self) -> None:
        if self._closed:
            raise ClientClosedError("xcron client is closed")


def _host(
    capability_registry: CapabilityRegistry | None,
    selection: CapabilitySelection | None,
) -> CapabilityHost:
    registry = capability_registry or CapabilityRegistry.from_entry_points()
    return CapabilityHost(registry, selection)


def _bootstrap_observability(host: CapabilityHost) -> None:
    """Let an installed observer bind the current stderr before scope warnings."""
    try:
        host.require("observability", ObservabilityPort).outcome_sink(InvocationContext(XcronOptions(), None, Settings()))
    except CapabilityUnavailableError:
        return None
    except Exception:
        return None


def _path(value: str | Path | None) -> Path | None:
    return None if value is None else Path(value).expanduser().resolve()


def _stated(value, default):
    return default if value is None else value


class _ObservedPort:
    """Translate a public port call into optional lifecycle observations."""

    def __init__(self, target: object, sink: OutcomeSink) -> None:
        self._target = target
        self._sink = sink

    def __getattr__(self, name: str) -> Any:
        member = getattr(self._target, name)
        if not callable(member):
            return member

        def observed(*args: Any, **kwargs: Any) -> Any:
            self._record("action_started", name)
            try:
                result = member(*args, **kwargs)
            except Exception:
                self._record("action_failed", name)
                raise
            self._record("action_finished", name)
            return result

        return observed

    def _record(self, event: str, action: str) -> None:
        try:
            self._sink.record(f"{event}:{action}")
        except Exception:
            return None

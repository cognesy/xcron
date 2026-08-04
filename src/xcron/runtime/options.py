"""Resolved invocation scope shared by xcron channels and capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class XcronOptions:
    """Immutable project and host options captured at runtime creation."""

    project_path: Path | None = None
    schedule_name: str | None = None
    backend: str | None = None
    state_root: Path | None = None
    platform: str | None = None
    launch_agents_dir: Path | None = None
    launchctl_domain: str | None = None
    crontab_path: Path | None = None
    manage_launchctl: bool = True
    manage_crontab: bool = True

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
    ) -> XcronOptions:
        return cls(
            project_path=_resolve_path(project_path),
            schedule_name=schedule_name,
            backend=backend,
            state_root=_resolve_path(state_root),
            platform=platform,
            launch_agents_dir=_resolve_path(launch_agents_dir),
            launchctl_domain=launchctl_domain,
            crontab_path=_resolve_path(crontab_path),
            manage_launchctl=manage_launchctl,
            manage_crontab=manage_crontab,
        )


def _resolve_path(value: str | Path | None) -> Path | None:
    return Path(value).expanduser().resolve() if value is not None else None
